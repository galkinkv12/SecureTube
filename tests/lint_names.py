import ast, builtins, sys
from pathlib import Path

BUILTINS = set(dir(builtins)) | {"__file__", "__name__"}

def targets(node, out):
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)): out.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)): out.add(n.name)
        elif isinstance(n, ast.arg): out.add(n.arg)
        elif isinstance(n, ast.ExceptHandler) and n.name: out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: out.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.Global): out.update(n.names)

def check(path):
    src = Path(path).read_text(encoding="utf-8"); tree = ast.parse(src)
    problems = []
    module_names = set(); targets(tree, module_names)
    # имена, определённые на уровне модуля (включая вложенные в функции Store — грубо, но безопасно)
    imported = {}
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                if a.name != "*" and getattr(n, "module", None) != "__future__": imported[(a.asname or a.name).split(".")[0]] = n.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    for name, line in imported.items():
        if name not in used and "__all__" not in src: problems.append(f"{path}:{line}: неиспользуемый импорт {name}")
    def visit(node, scope):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                local = set(); targets(child, local)
                visit(child, scope | local)
            elif isinstance(child, ast.ClassDef):
                local = set()
                for b in child.body: targets(b, local) if not isinstance(b,(ast.FunctionDef,)) else local.add(b.name)
                visit(child, scope)         
            else:
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    if child.id not in scope and child.id not in BUILTINS:
                        problems.append(f"{path}:{child.lineno}: необъявленное имя {child.id}")
                visit(child, scope)
    visit(tree, module_names)
    return problems

if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    files = sorted(root.glob("securetube/*.py")) + [root / "main.py", root / "tools" / "make_icon.py"]
    allp = []
    for f in files:
        if f.exists(): allp += check(f)
    print("\n".join(allp) or "линтер: замечаний нет")
    sys.exit(1 if allp else 0)
