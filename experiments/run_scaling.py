"""node count sweep measuring vector clock cost against system size"""

from causality_bench.experiments.runner import execute

if __name__ == "__main__":
    print(execute("configs/scaling.yaml"))
