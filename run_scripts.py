"""
Purpose
    Executes analysis scripts in an order based on explicit
    dependencies declared inside each script. This ensures that derived
    datasets and figures are generated in a reproducible sequence.

How it works
    Each analysis script in the analyse/ directory may declare dependencies
    in a single-line header of the form:
        # depends_on: other_script.py, another_script.py
    The dependency graph is topologically sorted. If a cycle is detected,
    execution stops with an explicit error to prevent ambiguous results.

Usage
    Run from the project root:
        python3 run_scripts.py
    The script will execute all .py files in analyse/ respecting declared
    dependencies; scripts without dependencies are executed first.
"""

import os
import re
from collections import defaultdict, deque

SCRIPT_DIR = 'analyse'

def parse_dependencies():
    deps = defaultdict(list)
    scripts = [f for f in os.listdir(SCRIPT_DIR) if f.endswith('.py')]

    for script in scripts:
        with open(os.path.join(SCRIPT_DIR, script)) as f:
            for line in f:
                match = re.match(r'# depends_on:\s*(.*)', line)
                if match:
                    dep_line = match.group(1).strip()
                    if dep_line:
                        deps[script] = [d.strip() for d in dep_line.split(',')]
                    break
    return deps, scripts

def topological_sort(deps, scripts):
    in_degree = {s: 0 for s in scripts}
    graph = defaultdict(list)

    for s, d_list in deps.items():
        for d in d_list:
            graph[d].append(s)
            in_degree[s] += 1

    q = deque([s for s in scripts if in_degree[s] == 0])
    sorted_scripts = []

    while q:
        node = q.popleft()
        sorted_scripts.append(node)
        for neighbor in graph[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                q.append(neighbor)

    if len(sorted_scripts) != len(scripts):
        raise Exception("Cycle detected in dependencies")

    return sorted_scripts

def run_scripts(scripts):
    for script in scripts:
        print(f"▶ Running {script}...")
        result = os.system(f'python3 {os.path.join(SCRIPT_DIR, script)}')
        exitcode = os.waitstatus_to_exitcode(result)
        if exitcode != 0:
            raise Exception("Python execution failed...")

if __name__ == '__main__':
    deps, scripts = parse_dependencies()
    ordered = topological_sort(deps, scripts)
    run_scripts(ordered)
