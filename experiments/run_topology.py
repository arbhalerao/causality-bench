"""communication structure sweep over five topologies"""

from causality_bench.experiments.runner import execute

if __name__ == "__main__":
    print(execute("configs/topology.yaml"))
