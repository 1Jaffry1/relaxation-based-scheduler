import heapq  # For priority queue operations
import csv  # For writing simulation results to a CSV file
from collections import deque
import statistics

# === Constants ===
NUM_CORES = 2
CONTEXT_SWITCH_TIME = 1
SIMULATION_TIME = 1000
epsilon = 1e-5
PREEMPT_DELTA_R = 1

# === Helper Functions ===

def compute_utilization(exec_history, ncores):
    if not exec_history:
        return 0.0, 0.0
    util_est = sum(exec_history) / (len(exec_history) * max(1, ncores))
    sigma_u = statistics.pstdev([e / max(1, ncores) for e in exec_history]) if len(exec_history) > 1 else 0.0
    return min(1.0, util_est), sigma_u

def calculate_adaptive_urgency(task, lambda_ ):
    laxity_norm = max(0, min(1, task.laxity / task.deadline))
    urgency = ( lambda_) * laxity_norm + (1-lambda_) * task.priority
    task.urgency = urgency
    return urgency

def update_lambda(utilization, rules):
    if utilization < rules['low_threshold']:
        return rules['low_lambda']
    elif utilization > rules['high_threshold']:
        return rules['high_lambda']
    else:
        return (rules['high_lambda'] - rules['low_lambda']) * (utilization - rules['low_threshold']) / \
               (rules['high_threshold'] - rules['low_threshold']) + rules['low_lambda']

def should_preempt(current_task, incoming_task, deltaR_threshold, now):
    if current_task is None:
        return True
    rt = current_task.remaining_time
    incoming_slack = incoming_task.tightened_deadline - (now - incoming_task.arrival_time)
    cannot_finish_before = incoming_slack > (rt - CONTEXT_SWITCH_TIME)
    relaxation_gap = (current_task.urgency) - (incoming_task.urgency)
    return cannot_finish_before and (relaxation_gap > deltaR_threshold)


# --- Globals for Summary ---
summary_log = []
missed_priorities_log = []

def simulate_taskset(taskset_id, taskset):
    unarrived_tasks = []
    for t in taskset:
        t.remaining_time = getattr(t, "burst_time", getattr(t, "exec_time", 1))
        t.arrival_time = int(getattr(t, "arrival_time", 0))
        t.deadline = int(getattr(t, "deadline", 10))
        t.priority = int(getattr(t, "priority", 2))
        t.id = getattr(t, "id", id(t))
        t.completion_time = None
        t.missed_deadline = False
        unarrived_tasks.append(t)

    ready_tasks = []
    cores = [None] * NUM_CORES

    print(f"\n🔵 EDF: Taskset #{taskset_id}\nt  1  |  2\n------|---")


    preemptions = 0
    deadline_misses = 0
    data_transfers = 0
    busy_time = 0
    failure_times = []
    completed_tasks = []
    missed_priorities = []
    wcrt = 0

    exec_hist = deque(maxlen=20)
    makespan = SIMULATION_TIME

    # Lambda adjustment rules
    lambda_rules = {
        'low_threshold': 0.1,
        'high_threshold': 0.5,
        'low_lambda': 0.05,
        'high_lambda': 0.7
    }

    for now in range(SIMULATION_TIME):
        for t in list(unarrived_tasks):
            if t.arrival_time <= now:
                heapq.heappush(ready_tasks, (t.deadline, t))
                unarrived_tasks.remove(t)

        window_exec = sum(1 for c in cores if c is not None)
        exec_hist.append(window_exec)
        util_est, sigma_u = compute_utilization(exec_hist, NUM_CORES)

        # Update lambda dynamically
        lambda_ = update_lambda(util_est, lambda_rules)

        # Update tightened deadlines and urgency
        for _, t in ready_tasks:
            abs_deadline = t.arrival_time + t.deadline
            t.tightened_deadline = abs_deadline * (1 - sigma_u)
            t.urgency = calculate_adaptive_urgency(t, lambda_)

        # Sort ready tasks by urgency
        ready_tasks = [(t.urgency, t) for _, t in ready_tasks]
        heapq.heapify(ready_tasks)

        for i in range(NUM_CORES):
            if cores[i] is None and ready_tasks:
                _, nxt = heapq.heappop(ready_tasks)
                nxt.remaining_time += CONTEXT_SWITCH_TIME
                cores[i] = nxt
                data_transfers += 1

        for i in range(NUM_CORES):
            running = cores[i]
            if running is not None and ready_tasks:
                _, cand = ready_tasks[0]
                if should_preempt(running, cand, deltaR_threshold=PREEMPT_DELTA_R, now=now):
                    heapq.heappush(ready_tasks, (running.urgency, running))
                    _, nxt = heapq.heappop(ready_tasks)
                    nxt.remaining_time += CONTEXT_SWITCH_TIME
                    cores[i] = nxt
                    preemptions += 1
                    data_transfers += 1

        for i in range(NUM_CORES):
            t = cores[i]
            if t is not None:
                t.remaining_time -= 1
                busy_time += 1
                if t.remaining_time <= 0:
                    t.completion_time = now + 1
                    completed_tasks.append(t)
                    abs_deadline = t.arrival_time + t.deadline
                    response_time = t.completion_time - t.arrival_time
                    wcrt = max(wcrt, response_time)
                    if t.completion_time > abs_deadline:
                        deadline_misses += 1
                        failure_times.append(now + 1)
                        missed_priorities.append(t.priority)
                    cores[i] = None

        core_status = [str(cores[i].id) if cores[i] else "-" for i in range(NUM_CORES)]
        print(f"{now}  {core_status[0]}  |  {core_status[1]}")

        if not unarrived_tasks and not ready_tasks and all(c is None for c in cores):
            makespan = now + 1
            break

    for t in taskset:
        if t.remaining_time > 0:
            deadline_misses += 1
            failure_times.append(makespan)
            missed_priorities.append(t.priority)

    mtbf = makespan / (deadline_misses + 1)

    summary_log.append([
        taskset_id,
        len(taskset),
        preemptions,
        deadline_misses,
        data_transfers,
        round(100.0 * (busy_time / (makespan * NUM_CORES)), 2),
        makespan,
        wcrt,
        mtbf
    ])
    missed_priorities_log.append((taskset_id, missed_priorities))

def main():
    from aperiodic_task_sets import tasks as tasksML
    for idx, ts in enumerate(tasksML, start=1):
        simulate_taskset(idx, ts)

    with open('optimized_schedule_summary.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Taskset_ID',
            'Taskset Size',
            'Preemptions',
            'Deadline_Misses',
            'Data_Transfers',
            'CPU_Utilization(%)',
            'Makespan',
            'WCRT',
            'MTBF',
            'Missed_Task_Priorities'
        ])
        for summary, (_, priorities) in zip(summary_log, missed_priorities_log):
            writer.writerow(summary + [','.join(str(p) for p in priorities)])

    print("\n✅ Saved optimized schedule summaries to 'optimized_schedule_summary.csv'")

if __name__ == "__main__":
    main()