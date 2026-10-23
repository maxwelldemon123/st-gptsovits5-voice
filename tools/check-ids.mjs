/**
 * 静态自检：node tools/check-ids.mjs
 *
 * 没有浏览器也要抓的低级错误：
 *  - getElementById 的 id 是否真的在面板里被创建过
 *  - manifest 引用的文件是否存在
 *  - event_types 名字是否在白名单里
 *  - 有没有 import 酒馆内部模块（本扩展的稳定性前提）
 *  - 是否误用了会重启服务端的 /control?command=restart
 */
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = readFileSync(join(root, 'index.js'), 'utf8');
const problems = [];
let checks = 0;

// 1) getElementById 的 id 必须有创建处
const HOST_IDS = new Set(['chat', 'top-settings-holder', 'top-bar', 'send_form', 'right-nav-panel']);
const used = new Set();
for (const m of src.matchAll(/getElementById\(\s*['"]([^'"]+)['"]\s*\)/g)) used.add(m[1]);
const created = new Set();
for (const m of src.matchAll(/\bid:\s*['"]([^'"]+)['"]/g)) created.add(m[1]);
for (const m of src.matchAll(/\bid="([^"]+)"/g)) created.add(m[1]);
for (const id of used) {
    if (HOST_IDS.has(id)) continue;
    checks++;
    if (!created.has(id)) problems.push(`getElementById('${id}') 没有对应的创建处`);
}

// 2) manifest
const manifest = JSON.parse(readFileSync(join(root, 'manifest.json'), 'utf8'));
for (const key of ['js', 'css']) {
    checks++;
    if (!manifest[key]) { problems.push(`manifest 缺少 ${key}`); continue; }
    if (!existsSync(join(root, manifest[key]))) problems.push(`manifest.${key} 指向的文件不存在`);
}
checks++;
if (!manifest.display_name) problems.push('manifest 缺少 display_name');
checks++;
if (!manifest.version) problems.push('manifest 缺少 version');

// 3) 事件名白名单
const KNOWN = new Set([
    'APP_READY', 'APP_INITIALIZED', 'CHAT_CHANGED', 'CHAT_CREATED', 'CHAT_DELETED',
    'CHARACTER_MESSAGE_RENDERED', 'USER_MESSAGE_RENDERED', 'MESSAGE_SWIPED',
    'MESSAGE_EDITED', 'MESSAGE_DELETED', 'CHARACTER_EDITED', 'CHARACTER_DELETED',
    'GENERATION_STARTED', 'GENERATION_ENDED',
]);
for (const m of src.matchAll(/event_types\.([A-Z_]+)/g)) {
    checks++;
    if (!KNOWN.has(m[1])) problems.push(`event_types.${m[1]} 不在白名单`);
}

// 4) 不 import 酒馆内部模块
checks++;
if (/from\s+['"][^'"]*\/script\.js['"]/.test(src) || /from\s+['"][^'"]*extensions\.js['"]/.test(src)) {
    problems.push('不要 import 酒馆内部模块，请用 SillyTavern.getContext()');
}

// 5) 绝不能调用会重启服务端的 control 命令
checks++;
if (/control\?command=(restart|exit)/.test(src)) problems.push('代码里出现了 /control?command=restart|exit，会重启服务端');

// 6) lib 存在且被引用
checks++;
if (!existsSync(join(root, 'lib', 'tts-text.js'))) problems.push('lib/tts-text.js 不存在');
checks++;
if (!/from\s+['"]\.\/lib\/tts-text\.js['"]/.test(src)) problems.push('index.js 没有引用 lib/tts-text.js');

console.log(`检查 ${checks} 项，问题 ${problems.length} 项`);
console.log(`使用的 id: ${[...used].sort().join(', ')}`);
if (problems.length) {
    for (const p of problems) console.error(' -', p);
    process.exit(1);
}
console.log('全部通过 ✅');
