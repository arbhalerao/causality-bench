"""reference experiment: one configuration, many independent seeds"""

from causality_bench.experiments.runner import execute

if __name__ == "__main__":
    print(execute("configs/baseline.yaml"))
