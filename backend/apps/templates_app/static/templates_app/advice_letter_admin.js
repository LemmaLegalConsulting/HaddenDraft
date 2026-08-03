(function () {
  "use strict";

  var BOLD = 1;
  var ITALIC = 2;
  var UNDERLINE = 8;

  function textNode(text, format) {
    return {
      detail: 0,
      format: format || 0,
      mode: "normal",
      style: "",
      text: text,
      type: "text",
      version: 1,
    };
  }

  function paragraphNode(children) {
    return {
      children: children,
      direction: "ltr",
      format: "",
      indent: 0,
      type: "paragraph",
      version: 1,
    };
  }

  function rootState(children) {
    return {
      root: {
        children: children,
        direction: "ltr",
        format: "",
        indent: 0,
        type: "root",
        version: 1,
      },
    };
  }

  function renderState(surface, state) {
    surface.replaceChildren();
    var children = state && state.root && Array.isArray(state.root.children)
      ? state.root.children
      : [paragraphNode([])];
    children.forEach(function (paragraph) {
      if (paragraph.type !== "paragraph") return;
      var element = document.createElement("p");
      (paragraph.children || []).forEach(function (child) {
        if (child.type === "linebreak") {
          element.appendChild(document.createElement("br"));
          return;
        }
        if (child.type !== "text") return;
        var node = document.createTextNode(child.text || "");
        var format = Number(child.format || 0);
        if (format & BOLD) {
          var bold = document.createElement("strong");
          bold.appendChild(node);
          node = bold;
        }
        if (format & ITALIC) {
          var italic = document.createElement("em");
          italic.appendChild(node);
          node = italic;
        }
        if (format & UNDERLINE) {
          var underline = document.createElement("u");
          underline.appendChild(node);
          node = underline;
        }
        element.appendChild(node);
      });
      if (!element.childNodes.length) element.appendChild(document.createElement("br"));
      surface.appendChild(element);
    });
    if (!surface.childNodes.length) surface.appendChild(document.createElement("p"));
  }

  function formatForElement(element) {
    var format = 0;
    var current = element;
    while (current && current.nodeType === 1) {
      var tag = current.tagName.toLowerCase();
      if (tag === "strong" || tag === "b") format |= BOLD;
      if (tag === "em" || tag === "i") format |= ITALIC;
      if (tag === "u") format |= UNDERLINE;
      current = current.parentElement;
    }
    return format;
  }

  function appendText(children, text, format) {
    if (!text) return;
    var previous = children[children.length - 1];
    if (previous && previous.type === "text" && previous.format === format) {
      previous.text += text;
    } else {
      children.push(textNode(text, format));
    }
  }

  function parseChildren(element) {
    var children = [];
    function visit(node) {
      if (node.nodeType === 3) {
        appendText(children, node.nodeValue || "", formatForElement(node.parentElement));
      } else if (node.nodeType === 1 && node.tagName.toLowerCase() === "br") {
        children.push({ type: "linebreak", version: 1 });
      } else if (node.nodeType === 1) {
        Array.prototype.forEach.call(node.childNodes, visit);
      }
    }
    Array.prototype.forEach.call(element.childNodes, visit);
    // A placeholder <br> is the browser's representation of an empty
    // paragraph, not an intentional line break in the Lexical state.
    if (children.length === 1 && children[0].type === "linebreak") return [];
    return children;
  }

  function stateFromSurface(surface) {
    var paragraphs = Array.prototype.map.call(surface.children, function (element) {
      return paragraphNode(parseChildren(element));
    });
    return rootState(paragraphs.length ? paragraphs : [paragraphNode([])]);
  }

  function plainText(state) {
    return (state.root.children || []).map(function (paragraph) {
      return (paragraph.children || []).map(function (child) {
        return child.type === "linebreak" ? "\n" : (child.text || "");
      }).join("");
    }).join("\n");
  }

  function setup(wrapper) {
    var stateField = wrapper.querySelector("textarea[name]");
    var bodyField = document.getElementById(wrapper.getAttribute("data-body-field"));
    var surface = wrapper.querySelector("[contenteditable]");
    var form = wrapper.closest("form");
    var state;
    try {
      state = JSON.parse(stateField.value || "{}");
    } catch (error) {
      state = {};
    }
    renderState(surface, state);
    var dirty = false;

    function sync() {
      state = stateFromSurface(surface);
      stateField.value = JSON.stringify(state);
      if (bodyField) bodyField.value = plainText(state);
    }

    surface.addEventListener("input", function () {
      dirty = true;
      sync();
    });
    wrapper.querySelectorAll("[data-rich-command]").forEach(function (button) {
      button.addEventListener("mousedown", function (event) {
        event.preventDefault();
        surface.focus();
        document.execCommand(button.getAttribute("data-rich-command"), false, null);
        dirty = true;
        sync();
      });
    });
    if (form) form.addEventListener("submit", function () {
      if (dirty) sync();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-advice-rich-editor]").forEach(setup);
  });
}());
