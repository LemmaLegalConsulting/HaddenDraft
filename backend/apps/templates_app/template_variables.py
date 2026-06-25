import re
from pathlib import Path

from docx import Document
from docxtpl import DocxTemplate
from jinja2 import Environment, TemplateSyntaxError, nodes
from jinja2.visitor import NodeVisitor

from apps.templates_app.word_templates import block_template_path, block_template_source


DOCXTPL_PREFIXES = ("p", "tr", "tc", "tbl", "r", "sectPr")
BLOCK_PREFIX_RE = re.compile(r"\{%\s*(?:" + "|".join(DOCXTPL_PREFIXES) + r")\b", re.IGNORECASE)
EXPR_PREFIX_RE = re.compile(r"(\{\{\s*)(?:" + "|".join(DOCXTPL_PREFIXES) + r")\s+", re.IGNORECASE)

SYSTEM_ROOTS = {
    "document",
    "section",
    "matter",
    "author",
    "selected_facts",
    "selected_curated_facts",
    "selected_sources",
    "instructions",
}
SYSTEM_ALIASES = {
    "court",
    "plaintiff",
    "defendant",
    "case_number",
    "advocate_name",
    "advocate_signoff",
    "advocate_salutation",
    "advocate_organization",
    "advocate_email",
    "advocate_phone",
    "advocate_address",
    "advocate_contact",
    "advocate_signature_image",
}


def normalize_docxtpl_blocks(text):
    text = BLOCK_PREFIX_RE.sub("{%", text)
    text = EXPR_PREFIX_RE.sub(r"\1", text)
    return text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")


class TemplateVarVisitor(NodeVisitor):
    IGNORE_ROOTS = {
        "loop",
        "cycler",
        "namespace",
        "range",
        "dict",
        "lipsum",
        "include_docx_template",
        "comma_and_list",
        "nice_number",
        "state_name",
        "defined",
        "showifdef",
    }

    def __init__(self, *, keep_calls=False):
        super().__init__()
        self.keep_calls = keep_calls
        self._loop_stack = []
        self.results = set()

    def visit_For(self, node, /):
        targets = self._targets(node.target)
        iter_expr = self._expr_to_str(node.iter)
        self._loop_stack.append({target: iter_expr for target in targets})
        self.generic_visit(node)
        self._loop_stack.pop()

    def visit_Getattr(self, node, /):
        chain = self._chain(node)
        if not chain:
            return
        root = self._resolve(chain[0])
        if self._ignored(root):
            return
        self.results.add(".".join([root, *chain[1:]]))

    def visit_Getitem(self, node, /):
        chain = self._chain(node)
        if not chain:
            self.generic_visit(node)
            return
        root = self._resolve(chain[0])
        if self._ignored(root):
            return
        self.results.add(".".join([root, *chain[1:]]))
        self.generic_visit(getattr(node, "arg", getattr(node, "slice", node)))

    def visit_Name(self, node, /):
        if node.ctx == "store" or self._ignored(node.name):
            return
        self.results.add(self._resolve(node.name))

    def visit_Call(self, node, /):
        self.generic_visit(node)
        if not self.keep_calls:
            return
        callee = self._expr_to_str(node.node)
        parts = callee.split(".")
        root, rest = parts[0], parts[1:]
        if self._ignored(root):
            return
        self.results.add(".".join([self._resolve(root), *rest]) + "()")

    @staticmethod
    def _targets(target):
        if isinstance(target, nodes.Name):
            return [target.name]
        if isinstance(target, nodes.Tuple):
            names = []
            for item in target.items:
                names.extend(TemplateVarVisitor._targets(item))
            return names
        return []

    def _resolve(self, name):
        base_name = name.split("[")[0] if "[" in name else name
        for stack_index, mapping in enumerate(reversed(self._loop_stack)):
            if base_name in mapping:
                if "[" in name:
                    return name
                depth_from_outer = len(self._loop_stack) - 1 - stack_index
                iterator_vars = ["i", "j", "k", "l", "m"]
                iterator_var = iterator_vars[depth_from_outer] if depth_from_outer < len(iterator_vars) else f"iter{depth_from_outer}"
                return f"{mapping[base_name]}[{iterator_var}]"
        return name

    def _expr_to_str(self, expr):
        if isinstance(expr, nodes.Name):
            return self._resolve(expr.name)
        if isinstance(expr, nodes.Getattr):
            chain = self._chain(expr)
            if chain:
                return ".".join([self._resolve(chain[0]), *chain[1:]])
        if isinstance(expr, nodes.Getitem):
            return self._expr_to_str(expr.node)
        if isinstance(expr, nodes.Call) and expr.node:
            return self._expr_to_str(expr.node)
        if isinstance(expr, nodes.Filter) and expr.node:
            return self._expr_to_str(expr.node)
        return "<expr>"

    @staticmethod
    def _chain(node):
        parts = []
        while True:
            if isinstance(node, nodes.Getattr):
                parts.insert(0, node.attr)
                node = node.node
            elif isinstance(node, nodes.Getitem):
                index_node = getattr(node, "arg", getattr(node, "slice", None))
                if index_node is not None:
                    index_value = getattr(index_node, "value", getattr(index_node, "n", None))
                    base_parts = TemplateVarVisitor._chain(node.node)
                    if base_parts and index_value is not None:
                        if isinstance(index_value, str):
                            base_parts[-1] = f'{base_parts[-1]}["{index_value}"]'
                        else:
                            base_parts[-1] = f"{base_parts[-1]}[{index_value}]"
                        return base_parts + parts
                node = node.node
            else:
                break
        if isinstance(node, nodes.Name):
            parts.insert(0, node.name)
        return parts

    def _ignored(self, variable):
        return variable.split(".", 1)[0].split("[", 1)[0] in self.IGNORE_ROOTS


def template_text_from_docx(path):
    path = Path(path)
    docx_template = DocxTemplate(path)
    document = Document(path)
    return docx_template.patch_xml(docx_template.xml_to_string(document._element.body))


def extract_template_variables_from_text(template_text, *, keep_calls=False):
    cleaned = normalize_docxtpl_blocks(template_text)
    ast = Environment().parse(cleaned)
    visitor = TemplateVarVisitor(keep_calls=keep_calls)
    visitor.visit(ast)
    variables = visitor.results
    if keep_calls:
        called_without_parens = {variable[:-2] for variable in variables if variable.endswith("()")}
        variables = variables - called_without_parens
    return sorted(_remove_redundant_roots(variables))


def extract_template_variables_from_docx(path, *, keep_calls=False):
    return extract_template_variables_from_text(template_text_from_docx(path), keep_calls=keep_calls)


def _remove_redundant_roots(variables):
    variable_set = set(variables)
    redundant = set()
    for variable in variable_set:
        root = variable.split(".", 1)[0]
        if any(other != variable and other.startswith(root + ".") for other in variable_set):
            redundant.add(root)
    return variable_set - redundant


def _root(variable):
    return variable.split(".", 1)[0].split("[", 1)[0]


def classify_template_variables(variables):
    provided = []
    external = []
    for variable in variables:
        root = _root(variable)
        if root in SYSTEM_ROOTS or variable in SYSTEM_ALIASES:
            provided.append(variable)
        else:
            external.append(variable)
    return {
        "all": variables,
        "providedBySystem": provided,
        "externalData": external,
    }


def block_variable_metadata(template, block):
    selected_path = block_template_path(template, block)
    if selected_path:
        try:
            variables = extract_template_variables_from_docx(selected_path)
            error = ""
        except (OSError, TemplateSyntaxError, ValueError) as exc:
            variables = []
            error = str(exc)
        return {
            "source": block_template_source(template, block),
            "name": Path(selected_path).name,
            "variables": classify_template_variables(variables),
            "parseError": error,
        }

    variables = extract_template_variables_from_text(block.body or "")
    return {
        "source": "body",
        "name": "",
        "variables": classify_template_variables(variables),
        "parseError": "",
    }


def template_variable_metadata(template):
    blocks = []
    all_variables = set()
    provided = set()
    external = set()
    for block in template.blocks.all():
        metadata = block_variable_metadata(template, block)
        variables = metadata["variables"]
        all_variables.update(variables["all"])
        provided.update(variables["providedBySystem"])
        external.update(variables["externalData"])
        blocks.append(
            {
                "key": block.key,
                "label": block.label,
                "blockType": block.block_type,
                **metadata,
            }
        )
    return {
        "variables": {
            "all": sorted(all_variables),
            "providedBySystem": sorted(provided),
            "externalData": sorted(external),
        },
        "blocks": blocks,
    }
