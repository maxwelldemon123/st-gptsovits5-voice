/**
 * 纯逻辑自测：node tools/test-text.mjs（不需要浏览器 / 酒馆 / 模型）
 */
import {
    extractSpeakableText, splitSentences, detectLang,
    readCardSlots, cardDefaultSlot, annotatedSlot, slotBlock,
    resolveSlotId, nextSlotId, normalizeBinding, parseSlotSpec,
    normalizeProfile, sameWeights, cacheKey, findProfile, slugId,
    clampSpeed, clampNum, LANGUAGES, DEFAULT_SLOT_ID,
} from '../lib/tts-text.js';

let passed = 0;
const failures = [];
function check(name, actual, expected) {
    const a = JSON.stringify(actual);
    const e = JSON.stringify(expected);
    if (a === e) passed++;
    else failures.push(`${name}\n  实际: ${a}\n  期望: ${e}`);
}

/* ---------------- 文本 ---------------- */
check('去掉全角括号动作', extractSpeakableText('（抱着小瓷碗）呜…主人…！'), '呜…主人…！');
check('嵌套括号不留残渣', extractSpeakableText('（她笑了一下（很浅））主人好'), '主人好');
check('星号动作去掉、粗体保留', extractSpeakableText('*叹气* **重要** 你好'), '重要你好');
check('代码块不朗读', extractSpeakableText('看这个\n```js\nx=1\n```\n好了'), '看这个好了');
check('方括号标签去掉', extractSpeakableText('[状态：好感+1] 她笑了'), '她笑了');
check('只读引号内', extractSpeakableText('她说："你回来了。" 又补「真慢」。', { readQuotedOnly: true }), '你回来了。真慢');
check('关掉过滤则原样', extractSpeakableText('（小声）呜', { stripActions: false }), '（小声）呜');
check('空输入', extractSpeakableText(null), '');
check('中文标点空格归一', extractSpeakableText('我 说 ， 好 的 。'), '我说，好的。');

check('断句：连用终止符不拆', splitSentences('呜…主人…！我一直在等着的。'), ['呜…主人…！', '我一直在等着的。']);
check('断句：过短合并', splitSentences('嗯。我在这里等着主人回来。'), ['嗯。我在这里等着主人回来。']);
check('断句：超长按逗号切', splitSentences('一'.repeat(50) + '，' + '二'.repeat(50), { maxLen: 60, minLen: 1 }),
    ['一'.repeat(50) + '，', '二'.repeat(50)]);
check('断句：空文本', splitSentences('  '), []);
check('断句：不切出超长段', splitSentences('啊'.repeat(500), { maxLen: 120, minLen: 1 }).every(s => s.length <= 120), true);

check('语种：假名→ja', detectLang('はい、そうです'), 'ja');
check('语种：汉字→zh', detectLang('呜…主人'), 'zh');
check('语种：谚文→ko', detectLang('안녕하세요'), 'ko');
check('语种：英文→en', detectLang('hello there'), 'en');
check('语言表含 ja', LANGUAGES.some(l => l.id === 'ja'), true);

/* ---------------- 声线槽位 ---------------- */
const cardNew = {
    data: { extensions: { gptsovits5: { defaultSlot: 'xiaod', slots: [{ id: 'xiaod', label: '小d · 柔软' }, { id: 'demon', label: 'demon · 小恶魔' }] } } },
};
const cardOld = {
    data: { extensions: { indextts25: { defaultSlot: 'demon', slots: [{ id: 'xiaod' }, { id: 'demon' }] } } },
};

check('读卡上新键', readCardSlots(cardNew).map(s => s.id), ['xiaod', 'demon']);
check('读卡上旧键（兼容）', readCardSlots(cardOld).map(s => s.id), ['xiaod', 'demon']);
check('新键优先', readCardSlots({ data: { extensions: { gptsovits5: { slots: [{ id: 'a' }] }, indextts25: { slots: [{ id: 'b' }] } } } }).map(s => s.id), ['a']);
check('无卡兜底', readCardSlots(null), [{ id: DEFAULT_SLOT_ID, label: '默认' }]);
check('卡默认槽位', cardDefaultSlot(cardNew), 'xiaod');
check('旧卡默认槽位', cardDefaultSlot(cardOld), 'demon');
check('重复 id 去重', readCardSlots({ data: { extensions: { gptsovits5: { slots: [{ id: 'a' }, { id: 'a' }, { id: 'b' }] } } } }).map(s => s.id), ['a', 'b']);
check('slotBlock 兼容顶层 extensions', slotBlock({ extensions: { gptsovits5: { slots: [] } } }) !== null, true);

check('消息标注：新键', annotatedSlot({ extra: { gptsovits5: { slot: 'demon' } } }), 'demon');
check('消息标注：旧键兼容', annotatedSlot({ extra: { indextts25: { slot: 'xiaod' } } }), 'xiaod');
check('消息标注：没有', annotatedSlot({ extra: {} }), '');

const slots = [{ id: 'xiaod' }, { id: 'demon' }];
const binding = { slots: { xiaod: { profileId: 'p1' }, demon: { profileId: 'p2' } }, activeSlot: '' };
check('标注优先', resolveSlotId({ message: { extra: { gptsovits5: { slot: 'demon' } } }, binding, slots, defaultSlot: 'xiaod' }), 'demon');
check('标注非法忽略', resolveSlotId({ message: { extra: { gptsovits5: { slot: 'x' } } }, binding, slots, defaultSlot: 'xiaod' }), 'xiaod');
check('手动激活优先于卡默认', resolveSlotId({ message: {}, binding: { ...binding, activeSlot: 'demon' }, slots, defaultSlot: 'xiaod' }), 'demon');
check('卡默认兜底', resolveSlotId({ message: {}, binding, slots, defaultSlot: 'demon' }), 'demon');
check('无默认时用已绑档案的槽', resolveSlotId({ message: {}, binding: { slots: { demon: { profileId: 'p2' } } }, slots, defaultSlot: '' }), 'demon');
check('都没绑时用第一个', resolveSlotId({ message: {}, binding: { slots: {} }, slots, defaultSlot: '' }), 'xiaod');

check('轮转', nextSlotId(slots, 'xiaod'), 'demon');
check('轮转绕回', nextSlotId(slots, 'demon'), 'xiaod');
check('单槽轮转', nextSlotId([{ id: 'default' }], 'default'), 'default');

check('旧绑定迁移（profileId）', normalizeBinding({ profileId: 'p1', speed: 1.2 }).slots.default.profileId, 'p1');
check('旧绑定迁移（voice 字段）', normalizeBinding({ voice: 'p1' }).slots.default.profileId, 'p1');
check('新绑定原样', normalizeBinding({ slots: { a: {} }, activeSlot: 'a' }).activeSlot, 'a');
check('null 绑定', normalizeBinding(null), null);
check('垃圾绑定', normalizeBinding({ foo: 1 }), null);

check('解析槽位定义', parseSlotSpec('xiaod:小d · 柔软, demon:demon · 小恶魔'), [
    { id: 'xiaod', label: '小d · 柔软' },
    { id: 'demon', label: 'demon · 小恶魔' },
]);
check('解析纯 id', parseSlotSpec('a,b，c；d').map(s => s.id), ['a', 'b', 'c', 'd']);
check('空串', parseSlotSpec(''), []);

/* ---------------- 音色档案 ---------------- */
const rawProfile = {
    id: 'xiaod', name: '小d · 柔软',
    gptWeights: 'GPT_SoVITS/pretrained_models/xiaod.ckpt',
    sovitsWeights: 'GPT_SoVITS/pretrained_models/xiaod.pth',
    refAudio: 'refs/xiaod.wav', promptText: 'はい、そうです', promptLang: 'ja',
};
const { profile, missing } = normalizeProfile(rawProfile);
check('档案归一化：无缺失', missing, []);
check('档案保留路径', profile.gptWeights, rawProfile.gptWeights);

const bad = normalizeProfile({ name: 'x' });
check('缺权重会被列出', bad.missing, ['GPT 权重', 'SoVITS 权重', '参考音频']);
check('参考语言默认 ja', bad.profile.promptLang, 'ja');
check('空 promptText 不算缺失', bad.missing.includes('参考文本'), false);

check('同权重判断（同）', sameWeights(profile, { ...profile, refAudio: 'other.wav' }), true);
check('同权重判断（异）', sameWeights(profile, { ...profile, gptWeights: 'b' }), false);
check('同权重判断（缺一）', sameWeights(profile, null), false);

const k1 = cacheKey(profile, { text: '你好', textLang: 'zh', speed: 1 });
const k2 = cacheKey(profile, { text: '你好', textLang: 'zh', speed: 1 });
const k3 = cacheKey(profile, { text: '你好', textLang: 'ja', speed: 1 });
const k4 = cacheKey(profile, { text: '再见', textLang: 'zh', speed: 1 });
check('缓存键稳定', k1, k2);
check('缓存键区分语言', k1 === k3, false);
check('缓存键区分文本', k1 === k4, false);

check('按 id 找档案', findProfile([profile], 'xiaod')?.name, '小d · 柔软');
check('按名字找档案', findProfile([profile], '小d · 柔软')?.id, 'xiaod');
check('找不到返回 null', findProfile([profile], 'nope'), null);

check('slugId 保中文', slugId('小d · 柔软'), '小d-柔软');
check('slugId 兜底', slugId('  '), 'profile');

check('语速夹上限', clampSpeed(9), 2);
check('语速夹下限', clampSpeed(0.1), 0.5);
check('数值夹取', clampNum('abc', 0, 1, 0.75), 0.75);

console.log(`通过 ${passed} 项`);
if (failures.length) {
    console.error(`失败 ${failures.length} 项：\n` + failures.map(f => ' - ' + f).join('\n'));
    process.exit(1);
}
console.log('全部通过 ✅');
