// jest-dom adds custom jest matchers for asserting on DOM nodes.
// allows you to do things like:
// expect(element).toHaveTextContent(/react/i)
// learn more: https://github.com/testing-library/jest-dom
import '@testing-library/jest-dom';

// --- jsdom shims for antd ---------------------------------------------------
// antd renders real components against browser APIs that jsdom implements
// partially. These stubs make the missing pieces behave, so a test that fails
// is failing about the application rather than about the DOM implementation.
// They belong here rather than in one test file: any antd Table, Modal or
// responsive component reaches them.

// `<Table scroll={{ x }}>` measures the scrollbar, and that measurement breaks
// jsdom twice over:
//
//  1. it calls `getComputedStyle(el, '::-webkit-scrollbar')`, and jsdom rejects
//     the pseudo-element argument;
//  2. it then injects a `#id::-webkit-scrollbar { }` rule into the document.
//
// The second one is the damaging half. To compute a style, jsdom walks every
// stylesheet in the document and asks its selector engine to match each rule.
// One rule it cannot parse makes *every later* `getComputedStyle` call throw,
// anywhere on the page — and the thrown error names neither stylesheets nor
// the rule. antd's Select ships a rule with the same problem, so this is not
// specific to Table.
//
// Real computed styles are returned whenever jsdom can produce them. The
// fallback covers only the two ways its CSS engine gives up on a rule that
// browsers accept, which is a limitation of the DOM implementation rather than
// a fact about the component under test. Anything else is re-thrown.
const EMPTY_STYLE = {
  width: '0px',
  height: '0px',
  getPropertyValue: () => '',
};

// "Failed to execute 'contains' on 'Node'" — an unparseable pseudo-element.
// "... is not a valid selector"           — a rule nwsapi cannot compile.
const JSDOM_CSS_LIMITS = /is not of type 'Node'|is not a valid selector/;

const realGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = function (element, pseudoElement) {
  if (pseudoElement) {
    return EMPTY_STYLE;
  }
  try {
    // `.call(window, ...)` matters: jsdom's implementation reads `this`.
    return realGetComputedStyle.call(window, element);
  } catch (error) {
    if (JSDOM_CSS_LIMITS.test(error.message)) {
      return EMPTY_STYLE;
    }
    throw error;
  }
};

// antd's responsive observers subscribe to media queries.
if (!window.matchMedia) {
  window.matchMedia = query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  });
}

// rc-resize-observer and rc-virtual-list both construct one.
if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
