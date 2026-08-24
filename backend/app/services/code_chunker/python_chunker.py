import ast

from backend.app.schemas.code import CodeChunk, CodeChunkResult
from backend.app.services.code_parser import PythonCodeParser


class PythonCodeChunker:
    def __init__(self, parser: PythonCodeParser | None = None) -> None:
        self.parser = parser or PythonCodeParser()

    def chunk(self, source: str, filename: str) -> CodeChunkResult:
        tree = self.parser.parse_tree(source, filename)
        lines = source.splitlines()
        chunks: list[CodeChunk] = []

        imports = [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]
        variables = [
            node
            for node in tree.body
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign))
        ]
        top_level_structures = [
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        handled = {*imports, *variables, *top_level_structures}
        module_groups: list[list[ast.stmt]] = []
        for index, node in enumerate(tree.body):
            if node in handled:
                continue
            if index == 0 or tree.body[index - 1] in handled:
                module_groups.append([])
            module_groups[-1].append(node)

        if imports:
            chunks.append(self._make_chunk("imports", "imports", imports, lines, filename))
        if variables:
            chunks.append(
                self._make_chunk("variables", "variables", variables, lines, filename)
            )

        for node in top_level_structures:
            if isinstance(node, ast.ClassDef):
                chunks.append(
                    self._make_chunk(
                        "class", node.name, [node], lines, filename, class_name=node.name
                    )
                )
                for method in node.body:
                    if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        chunks.append(
                            self._make_chunk(
                                "method",
                                method.name,
                                [method],
                                lines,
                                filename,
                                parent=node.name,
                                class_name=node.name,
                                function_name=method.name,
                            )
                        )
                        chunks.extend(
                            self._nested_chunks(
                                method,
                                lines,
                                filename,
                                parent=f"{node.name}.{method.name}",
                                class_name=node.name,
                            )
                        )
            else:
                chunks.append(
                    self._make_chunk(
                        "async_function" if isinstance(node, ast.AsyncFunctionDef) else "function",
                        node.name,
                        [node],
                        lines,
                        filename,
                        function_name=node.name,
                    )
                )
                chunks.extend(
                    self._nested_chunks(
                        node, lines, filename, parent=node.name, function_name=node.name
                    )
                )

        for index, module_code in enumerate(module_groups, start=1):
            chunks.append(
                self._make_chunk(
                    "module",
                    "module" if index == 1 else f"module_{index}",
                    module_code,
                    lines,
                    filename,
                )
            )

        chunks.sort(key=lambda chunk: (chunk.start_line, chunk.end_line, chunk.chunk_type))
        return CodeChunkResult(
            success=True,
            filename=filename,
            language="python",
            chunks=chunks,
        )

    def _nested_chunks(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        lines: list[str],
        filename: str,
        parent: str,
        class_name: str | None = None,
        function_name: str | None = None,
    ) -> list[CodeChunk]:
        chunks = []
        for child in ast.walk(node):
            if child is node or not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            chunks.append(
                self._make_chunk(
                    "nested_async_function" if isinstance(child, ast.AsyncFunctionDef) else "nested_function",
                    child.name,
                    [child],
                    lines,
                    filename,
                    parent=parent,
                    class_name=class_name,
                    function_name=child.name,
                )
            )
        return chunks

    @staticmethod
    def _make_chunk(
        chunk_type: str,
        name: str,
        nodes: list[ast.AST],
        lines: list[str],
        filename: str,
        parent: str | None = None,
        class_name: str | None = None,
        function_name: str | None = None,
    ) -> CodeChunk:
        start_line = min(node.lineno for node in nodes)
        end_line = max(getattr(node, "end_lineno", node.lineno) for node in nodes)
        content = "\n".join(lines[start_line - 1 : end_line])
        suffix = name if parent is None else f"{parent}.{name}"
        return CodeChunk(
            chunk_id=f"{filename}:{chunk_type}:{suffix}",
            filename=filename,
            language="python",
            chunk_type=chunk_type,
            name=name,
            start_line=start_line,
            end_line=end_line,
            content=content,
            parent=parent,
            class_name=class_name,
            function_name=function_name,
        )
