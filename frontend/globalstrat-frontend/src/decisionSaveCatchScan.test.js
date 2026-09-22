/**
 * No student save may fail into a catch block that throws the error away.
 *
 * V2-107 and the 2026-09-21 silent-section-saves finding are the same defect:
 * a page saved a decision, the server refused it, the page's
 * `catch { /* ignore *\/ }` said nothing, and the number stayed on the screen
 * as though it had been stored. Two whole decisions (staff allocation and
 * compliance investment) were refused on EVERY save for as long as they
 * existed, and no one was told.
 *
 * This reads the source of every page and context as a syntax tree, so it is
 * not fooled by comments, strings or formatting. For every `try` whose body
 * issues a student write it requires the `catch` to bind the error and to use
 * it; and it refuses a `.catch(() => ...)` chained straight onto such a write.
 * "Use it" is deliberately loose -- hand it to `reportUnpublishedFailure`, put
 * the server's sentences on screen, re-throw it -- because what is forbidden
 * is exactly one thing: discarding it.
 *
 * The axios interceptor (api/client.js) already announces a refused decision
 * write to the shared notice. This guard is about what the interceptor cannot
 * see -- a failure that never became a request -- and about keeping each page
 * honest so that the shared notice is never the only thing standing between a
 * student and a lost round.
 */
const fs = require('fs');
const path = require('path');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;

const SRC = __dirname;
const SCANNED_DIRS = ['pages', 'contexts'];

/** Functions from src/api that write a student decision. */
const SAVE_FUNCTIONS = new Set([
  'patchDecision', 'saveDecisions', 'lockDecisions',
  'setTaxStructure', 'switchOrgStructure',
  'saveCommunicationDraft', 'submitCommunication',
  'purchaseResearchReport',
  'saveSourcing', 'saveLogistics', 'saveTradeFinance', 'saveInventory',
  // Page-local wrappers around the above.
  'sendSave', 'sendDraft',
]);
/**
 * Direct axios writes. `client.request(config)` re-sends a refused save, so it
 * always counts; the verbs count when their URL is a student decision route.
 * A page's own notes (the strategy-tools worksheets) are not a decision and
 * are left to that page.
 */
const CLIENT_WRITE_METHODS = new Set(['post', 'patch', 'put', 'delete']);
const DECISION_ROUTE = /\/(decisions|sc\/round|context|communications|research|products)\//;

const urlText = (node) => {
  if (!node) return '';
  if (node.type === 'StringLiteral') return node.value;
  if (node.type === 'TemplateLiteral') {
    return node.quasis.map((q) => q.value.cooked).join('${}');
  }
  return '';
};

const sourceFiles = () => SCANNED_DIRS.flatMap((dir) => fs
  .readdirSync(path.join(SRC, dir))
  .filter((name) => /\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name))
  .map((name) => path.join(dir, name)));

const parse = (code) => parser.parse(code, {
  sourceType: 'module', plugins: ['jsx'], errorRecovery: false,
});

const isSaveCall = (node) => {
  if (node.type !== 'CallExpression') return false;
  const { callee } = node;
  if (callee.type === 'Identifier') return SAVE_FUNCTIONS.has(callee.name);
  if (callee.type === 'MemberExpression' && !callee.computed
      && callee.object.type === 'Identifier' && callee.object.name === 'client'
      && callee.property.type === 'Identifier') {
    if (callee.property.name === 'request') return true;
    return CLIENT_WRITE_METHODS.has(callee.property.name)
      && DECISION_ROUTE.test(urlText(node.arguments[0]));
  }
  return false;
};

/** Does this subtree contain a save call, not counting nested functions'
 *  own try blocks (those are judged on their own)? */
const containsSaveCall = (nodePath) => {
  let found = null;
  nodePath.traverse({
    CallExpression(inner) {
      if (isSaveCall(inner.node)) { found = inner.node; inner.stop(); }
    },
    TryStatement(inner) { inner.skip(); },
  });
  return found;
};

const usesBinding = (handlerPath) => {
  const param = handlerPath.node.param;
  if (!param || param.type !== 'Identifier') return false;
  const binding = handlerPath.scope.getBinding(param.name);
  return Boolean(binding && binding.referencePaths.length > 0);
};

/** Every place in `code` where a save's failure is discarded. */
const findDiscardedSaveFailures = (code) => {
  const problems = [];
  traverse(parse(code), {
    TryStatement(tryPath) {
      const save = containsSaveCall(tryPath.get('block'));
      if (!save) return;
      const handler = tryPath.get('handler');
      if (!handler.node) {
        problems.push({ line: tryPath.node.loc.start.line,
          why: 'try/finally around a save with no catch at all' });
        return;
      }
      if (!usesBinding(handler)) {
        problems.push({ line: handler.node.loc.start.line,
          why: 'catch discards the error of a save' });
      }
    },
    CallExpression(callPath) {
      // save(...).catch(() => ...) and save(...).then(...).catch(() => ...)
      const { callee } = callPath.node;
      if (callee.type !== 'MemberExpression' || callee.computed
          || callee.property.name !== 'catch') return;
      let chain = callee.object;
      while (chain.type === 'CallExpression' && !isSaveCall(chain)
             && chain.callee.type === 'MemberExpression') {
        chain = chain.callee.object;
      }
      if (!isSaveCall(chain)) return;
      const [fn] = callPath.get('arguments');
      const takesError = fn && fn.isFunction() && fn.node.params.length > 0
        && fn.node.params[0].type === 'Identifier'
        && fn.scope.getBinding(fn.node.params[0].name).referencePaths.length > 0;
      if (!takesError) {
        problems.push({ line: callPath.node.loc.start.line,
          why: '.catch() discards the error of a save' });
      }
    },
  });
  return problems;
};

describe('the scanner itself', () => {
  const find = (code) => findDiscardedSaveFailures(code).map((p) => p.why);

  it('flags the defect verbatim', () => {
    expect(find(`
      const autoSave = async () => {
        try { await patchDecision(1, 2, 3, 'esg', {}); refreshBudgets(); }
        catch { /* ignore */ }
      };`)).toEqual(['catch discards the error of a save']);
  });

  it('flags a bound but unused error', () => {
    expect(find(`
      async function f() {
        try { await saveDecisions(1, 2, 3, {}); } catch (err) { setSaving(false); }
      }`)).toEqual(['catch discards the error of a save']);
  });

  it('flags a console-free swallow on a direct client write', () => {
    expect(find(`
      async function f() {
        try { await client.post(\`/games/\${g}/teams/\${t}/decisions/round/1/\`, {}); } catch (e) {}
      }`)).toEqual(['catch discards the error of a save']);
  });

  it('flags a chained catch that ignores the error', () => {
    expect(find('setTaxStructure(1, 2, "x").then(() => done()).catch(() => {});'))
      .toEqual(['.catch() discards the error of a save']);
  });

  it('flags a try/finally with no catch', () => {
    expect(find(`
      async function f() {
        try { await lockDecisions(1, 2, 3); } finally { setBusy(false); }
      }`)).toEqual(['try/finally around a save with no catch at all']);
  });

  it('accepts a catch that uses the error', () => {
    expect(find(`
      async function f() {
        try { await patchDecision(1, 2, 3, 'esg', {}); }
        catch (err) { reportUnpublishedFailure(err); }
      }`)).toEqual([]);
  });

  it('leaves a page\'s own worksheet notes to that page', () => {
    expect(find(`
      async function f() {
        try { await client.post(\`/games/\${g}/teams/\${t}/tools/analysis/\`, {}); }
        catch { message.error('x'); }
      }`)).toEqual([]);
  });

  it('does not judge a read', () => {
    expect(find(`
      async function f() {
        try { const res = await getDecisions(1, 2, 3); use(res); } catch { /* a read */ }
      }`)).toEqual([]);
  });

  it('judges a nested try on its own, not its parent', () => {
    expect(find(`
      async function f() {
        try {
          load();
          try { await patchDecision(1, 2, 3, 'esg', {}); } catch (err) { show(err); }
        } catch { /* a read */ }
      }`)).toEqual([]);
  });
});

describe('every page and context', () => {
  const files = sourceFiles();

  it('finds the files it is meant to scan', () => {
    expect(files).toEqual(expect.arrayContaining([
      path.join('pages', 'MarketStrategyPage.js'),
      path.join('pages', 'CorporateStrategyPage.js'),
      path.join('contexts', 'DecisionContext.js'),
    ]));
  });

  it.each(files)('%s never discards the failure of a save', (relative) => {
    const code = fs.readFileSync(path.join(SRC, relative), 'utf8');
    const problems = findDiscardedSaveFailures(code)
      .map((p) => `${relative}:${p.line} ${p.why}`);
    expect(problems).toEqual([]);
  });
});
