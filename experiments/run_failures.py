"""message loss and crash-recovery failure sweep"""

from causality_bench.experiments.runner import execute

if __name__ == "__main__":
    print(execute("configs/failure.yaml"))
