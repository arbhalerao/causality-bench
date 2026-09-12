"""communication intensity sweep"""

from causality_bench.experiments.runner import execute

if __name__ == "__main__":
    print(execute("configs/message_rate.yaml"))
