# causality-bench

Lamport clocks and vector clocks both order events in a distributed system by causality rather than by wall-clock time. Lamport clocks are one integer; vector clocks are one integer per node. The tradeoff is textbook, but the size of it usually isn't quantified.

This benchmark quantifies it. A simulator runs a distributed workload and records the actual happens-before relation of that execution, derived from program order and message delivery only. Both clocks run over the same execution and are scored against that record.

---

## architecture

```
configs/*.yaml
      |
      v
simulation/     topology, network, deterministic event queue
                node runs BOTH clocks over ONE execution
      |
      +---> events (timestamped) ----+
      |                              |
      +---> events (dependencies)    |
                  |                  |
                  v                  |
            causality/dag            |
            ground truth from        |
            program order and        |
            send->receive ONLY       |
                  |                  |
                  +--------+---------+
                           v
                  experiments/metrics
                  exact pair counts, no sampling
                           |
       results/raw -> statistics -> results/processed
                                          |
                              visualization -> results/figures
```

`causality/` does not import from `clocks/`. The ground truth is computed from the execution structure, not from the timestamps being evaluated.

---

## how the ground truth is built

Each event stores its direct causes: the previous event on the same node, and for a receive, the matching send. Those are the two edge types in the definition of `->`.

Answering `a -> b` by graph search is O(V+E) per query, which is too slow for every pair of a few thousand events. Instead a single pass over the events builds an index holding, per event, how far into each node its causal past reaches. Queries become one array lookup. The tests verify the index against breadth-first search for every pair of a small execution, and against the edge count of NetworkX's transitive closure.

Pairs are counted exhaustively rather than sampled.

---

## what is measured

| metric              | definition                                                   |
| ------------------- | ------------------------------------------------------------ |
| causal density      | ordered pairs / all pairs                                    |
| concurrency ratio   | concurrent pairs / all pairs                                 |
| false ordering rate | of genuinely concurrent pairs, the share a clock separates   |
| concurrency recall  | of genuinely concurrent pairs, the share reported concurrent |
| order precision     | of pairs a clock orders, the share genuinely causal          |
| causal recall       | of genuinely ordered pairs, the share ordered correctly      |

---

## running it

```bash
make install
make check
make reproduce     # six experiments, then aggregation, then figures
```

Individual stages are `make experiments`, `make analysis`, `make figures`. Individual experiments are `.venv/bin/python experiments/run_baseline.py` and the same for `scaling`, `message_rate`, `delay`, `topology`, `failures`.

Experiments run sequentially. Each record includes wall-clock timings, which parallel execution would distort.

Each experiment is a YAML file in [`configs/`](configs). The same config and seed reproduce a run exactly; there is a test for this.

---

## limitations

1. **Simulation, not deployment.** No sockets, no scheduler, no clock drift. The ordering results are properties of the executions and hold generally. The nanosecond timings are properties of one machine and do not.
2. **Cost measured in Python.** The O(1) against O(N) difference would survive a rewrite. The constants would not.
3. **Memory is a lower bound**, since CPython reuses small integers.
4. **Synthetic workload**: uniform neighbour selection, exponential inter-event gaps. Real traffic has request/response structure and bursts.
5. **One parameter varies at a time.** Interactions between parameters are not covered.
6. **Dense vectors only.** Compression schemes are discussed but not measured.

---

## possible future work

- Measure the standard compressions (differential vectors, Singhal-Kshemkalyani, plausible clocks) on this harness, so their error rates are comparable to the two exact schemes.
- Re-measure cost in a compiled language to separate algorithmic cost from interpreter overhead.
- Replace the synthetic workload with a request/response trace.
- Add network partitions to the failure model.

---

## references

1. L. Lamport. Time, clocks, and the ordering of events in a distributed system. *CACM* 21(7), 1978.
2. C. J. Fidge. Timestamps in message-passing systems that preserve the partial ordering. *ACSC*, 1988.
3. F. Mattern. Virtual time and global states of distributed systems, 1989.
4. M. Singhal, A. Kshemkalyani. An efficient implementation of vector clocks. *IPL* 43(1), 1992.
5. B. Charron-Bost. Concerning the size of logical clocks in distributed systems. *IPL* 39(1), 1991.
