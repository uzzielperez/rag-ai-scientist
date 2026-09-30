'use strict';

/**
 * Overleaf Git client used by the custom overleaf-mcp server.
 * Clones/pulls git.overleaf.com/<projectId> into a local mirror and
 * exposes read/write helpers for LaTeX + binary assets.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execFileSync, spawnSync } = require('child_process');

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, {
    cwd: opts.cwd,
    encoding: 'utf8',
    env: opts.env || process.env,
  });
  if (result.status !== 0) {
    const err = (result.stderr || result.stdout || '').trim() || `${cmd} failed`;
    throw new Error(err);
  }
  return (result.stdout || '').trim();
}

class OverleafGitClient {
  /**
   * @param {string} gitToken
   * @param {string} projectId
   * @param {string|null} mirrorDir
   * @param {string} gitHost
   */
  constructor(gitToken, projectId, mirrorDir = null, gitHost = 'git.overleaf.com') {
    if (!gitToken) throw new Error('gitToken is required');
    if (!projectId) throw new Error('projectId is required');
    this.gitToken = gitToken;
    this.projectId = projectId;
    this.gitHost = gitHost;
    this.mirrorDir =
      mirrorDir ||
      path.join(os.homedir(), '.cache', 'overleaf-mcp', projectId);
  }

  get remoteUrl() {
    const token = encodeURIComponent(this.gitToken);
    return `https://git:${token}@${this.gitHost}/${this.projectId}`;
  }

  get maskedRemote() {
    return `https://git:***@${this.gitHost}/${this.projectId}`;
  }

  ensureMirror({ reset = false } = {}) {
    fs.mkdirSync(path.dirname(this.mirrorDir), { recursive: true });
    const gitDir = path.join(this.mirrorDir, '.git');
    if (fs.existsSync(gitDir)) {
      if (!reset) {
        // Keep local edits (write_file / upload_file) so a later commit can see them.
        return this.mirrorDir;
      }
      try {
        run('git', ['fetch', 'origin'], { cwd: this.mirrorDir });
        try {
          run('git', ['reset', '--hard', 'origin/master'], { cwd: this.mirrorDir });
        } catch {
          run('git', ['reset', '--hard', 'origin/main'], { cwd: this.mirrorDir });
        }
      } catch (err) {
        // Fall through to fresh clone if fetch fails hard
        fs.rmSync(this.mirrorDir, { recursive: true, force: true });
        run('git', ['clone', this.remoteUrl, this.mirrorDir]);
      }
      return this.mirrorDir;
    }
    run('git', ['clone', this.remoteUrl, this.mirrorDir]);
    return this.mirrorDir;
  }

  /**
   * Refresh from remote (destructive). Use before read-only inspection when you
   * want the cloud copy, not local uncommitted edits.
   */
  pullFresh() {
    return this.ensureMirror({ reset: true });
  }

  _safePath(relPath) {
    if (!relPath || typeof relPath !== 'string') {
      throw new Error('path must be a non-empty string');
    }
    if (relPath.includes('..') || path.isAbsolute(relPath)) {
      throw new Error('path must be relative and cannot contain ".."');
    }
    const full = path.resolve(this.mirrorDir, relPath);
    const root = path.resolve(this.mirrorDir);
    if (!full.startsWith(root + path.sep) && full !== root) {
      throw new Error('path escapes project root');
    }
    return full;
  }

  async listFiles(extension = '.tex') {
    this.pullFresh();
    const out = [];
    const walk = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        if (entry.name === '.git') continue;
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          walk(full);
        } else if (!extension || entry.name.endsWith(extension)) {
          out.push(path.relative(this.mirrorDir, full).split(path.sep).join('/'));
        }
      }
    };
    walk(this.mirrorDir);
    return out.sort();
  }

  async readFile(filePath) {
    this.pullFresh();
    const full = this._safePath(filePath);
    if (!fs.existsSync(full)) throw new Error(`File not found: ${filePath}`);
    return fs.readFileSync(full, 'utf8');
  }

  async writeFile(filePath, content) {
    this.ensureMirror();
    const full = this._safePath(filePath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.writeFileSync(full, content, 'utf8');
    return full;
  }

  async deleteFile(filePath) {
    this.ensureMirror();
    const full = this._safePath(filePath);
    if (!fs.existsSync(full)) throw new Error(`File not found: ${filePath}`);
    fs.unlinkSync(full);
    return true;
  }

  async copyFileInto(srcPath, destPath) {
    this.ensureMirror();
    const full = this._safePath(destPath);
    fs.mkdirSync(path.dirname(full), { recursive: true });
    fs.copyFileSync(srcPath, full);
    return full;
  }

  _parseSections(tex) {
    const lines = tex.split(/\r?\n/);
    const sections = [];
    let current = null;
    const startRe = /^\\(part|chapter|section|subsection|subsubsection)\*?\{/;

    const flush = () => {
      if (current) {
        current.content = current._buf.join('\n');
        delete current._buf;
        sections.push(current);
      }
    };

    for (const line of lines) {
      const m = line.match(startRe);
      if (m) {
        flush();
        const type = m[1];
        const brace = line.indexOf('{');
        let depth = 0;
        let title = '';
        for (let i = brace; i < line.length; i++) {
          const ch = line[i];
          if (ch === '{') depth++;
          else if (ch === '}') {
            depth--;
            if (depth === 0) break;
          } else if (depth >= 1) {
            if (!(depth === 1 && ch === '{')) title += ch;
          }
        }
        // Simpler title extract
        const tm = line.match(/\\(?:part|chapter|section|subsection|subsubsection)\*?\{([^}]*)\}/);
        title = tm ? tm[1] : title;
        current = { type, title, content: '', _buf: [] };
      } else if (current) {
        current._buf.push(line);
      }
    }
    flush();
    return sections;
  }

  async getSections(filePath) {
    const tex = await this.readFile(filePath);
    return this._parseSections(tex);
  }

  async getSection(filePath, sectionTitle) {
    const sections = await this.getSections(filePath);
    const needle = String(sectionTitle).trim().toLowerCase();
    return (
      sections.find((s) => s.title.trim().toLowerCase() === needle) ||
      sections.find((s) => s.title.trim().toLowerCase().includes(needle)) ||
      null
    );
  }

  async commit(message) {
    this.ensureMirror();
    run('git', ['add', '-A'], { cwd: this.mirrorDir });
    const porcelain = run('git', ['status', '--porcelain'], { cwd: this.mirrorDir });
    if (!porcelain) return 'Nothing to commit (clean working tree).';
    run(
      'git',
      [
        '-c',
        'user.name=Overleaf MCP',
        '-c',
        'user.email=overleaf-mcp@local',
        'commit',
        '-m',
        message,
      ],
      { cwd: this.mirrorDir }
    );
    return run('git', ['log', '-1', '--oneline'], { cwd: this.mirrorDir });
  }

  async push() {
    this.ensureMirror();
    try {
      return run('git', ['push', 'origin', 'HEAD:master'], { cwd: this.mirrorDir });
    } catch {
      return run('git', ['push', 'origin', 'HEAD:main'], { cwd: this.mirrorDir });
    }
  }

  async status() {
    this.ensureMirror({ reset: false });
    // Show true local status (may include uncommitted writes).
    const branch = run('git', ['rev-parse', '--abbrev-ref', 'HEAD'], { cwd: this.mirrorDir });
    const head = run('git', ['rev-parse', '--short', 'HEAD'], { cwd: this.mirrorDir });
    const porcelain = run('git', ['status', '--porcelain'], { cwd: this.mirrorDir });
    return [
      `remote: ${this.maskedRemote}`,
      `branch: ${branch}`,
      `head: ${head}`,
      `dirty: ${porcelain ? 'yes' : 'no'}`,
      porcelain || '(clean)',
    ].join('\n');
  }
}

module.exports = OverleafGitClient;
