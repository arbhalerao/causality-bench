"""network delay sweep over delay laws and delay magnitudes"""

from causality_bench.experiments.runner import execute

if __name__ == "__main__":
    print(execute("configs/delay.yaml"))
