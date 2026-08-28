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
//  2. it then injects a `#id::-webkit-scrollbar { }` rule into the document,
//     and jsdom's selector engine cannot parse that pseudo-element — so every
//     *later* `getComputedStyle` call throws too, anywhere in the page.
//
// The second one is why the failure is so misleading: it surfaces as
// "Failed to execute 'contains' on 'Node'" from deep inside rc-table, with a
// perfectly ordinary element as the argument and no mention of stylesheets.
//
// Real computed styles are still returned whenever jsdom can produce them. The
// fallback applies only once that unparseable rule is in the document, which is
// a limitation of the DOM implementation and not a fact about the component.
const EMPTY_STYLE = {
  width: '0px',
  height: '0px',
  getPropertyValue: () => '',
};

const realGetComputedStyle = window.getComputedStyle;
window.getComputedStyle = function (element, pseudoElement) {
  if (pseudoElement) {
    return EMPTY_STYLE;
  }
  try {
    // `.call(window, ...)` matters: jsdom's implementation reads `this`.
    return realGetComputedStyle.call(window, element);
  } catch (error) {
    if (/is not of type 'Node'/.test(error.message)) {
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
