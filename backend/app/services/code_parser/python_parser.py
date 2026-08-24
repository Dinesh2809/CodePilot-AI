import ast

from backend.app.schemas.code import (
    CodeClass,
    CodeFunction,
    CodeImport,
    CodeParseResult,
    CodeVariable,
    FunctionArgument,
)


class PythonCodeParser:
    def parse_tree(self, source: str, filename: str) -> ast.Module:
        try:
            return ast.parse(source, filename=filename)
        except SyntaxError as error:
            message = "Unable to parse Python source code"
            if error.lineno is not None:
                message += f" at line {error.lineno}"
            raise ValueError(message) from None

    def parse(self, source: str, filename: str, line_count: int) -> CodeParseResult:
        tree = self.parse_tree(source, filename)

        functions = []
        classes = []
        imports = []
        variables = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(self._function(node))
                functions.extend(self._nested_functions(node))
            elif isinstance(node, ast.ClassDef):
                classes.append(self._class(node))
            elif isinstance(node, ast.Import):
                imports.extend(
                    CodeImport(module=alias.name, type="import")
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom):
                module = "." * node.level + (node.module or "")
                imports.extend(
                    CodeImport(module=module, name=alias.name, type="from_import")
                    for alias in node.names
                )
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                variables.extend(self._variables(node))

        return CodeParseResult(
            success=True,
            language="python",
            file={"filename": filename, "line_count": line_count},
            imports=imports,
            functions=functions,
            classes=classes,
            variables=variables,
        )

    def _class(self, node: ast.ClassDef) -> CodeClass:
        methods = [
            self._function(child)
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        return CodeClass(
            name=node.name,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", None),
            bases=[self._expression(base) for base in node.bases],
            methods=methods,
            decorators=[self._expression(decorator) for decorator in node.decorator_list],
        )

    def _function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> CodeFunction:
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        return CodeFunction(
            name=node.name,
            line=node.lineno,
            end_line=getattr(node, "end_lineno", None),
            arguments=[
                FunctionArgument(
                    name=argument.arg,
                    annotation=self._expression(argument.annotation),
                )
                for argument in arguments
            ],
            return_annotation=self._expression(node.returns),
            decorators=[self._expression(decorator) for decorator in node.decorator_list],
            is_async=isinstance(node, ast.AsyncFunctionDef),
        )

    def _nested_functions(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[CodeFunction]:
        nested = []
        for child in ast.walk(node):
            if child is node:
                continue
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                nested.append(self._function(child))
        return nested

    def _variables(self, node: ast.Assign | ast.AnnAssign) -> list[CodeVariable]:
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        names = []
        for target in targets:
            if isinstance(target, ast.Name):
                names.append(CodeVariable(name=target.id, line=target.lineno))
        return names

    @staticmethod
    def _expression(node: ast.expr | None) -> str | None:
        return ast.unparse(node) if node is not None else None