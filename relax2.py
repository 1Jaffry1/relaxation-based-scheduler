import heapq
from taskset import tasks as tasksML
from taskset import SIMULATION_TIME
import csv

# Configuration
NUM_CORES = 2
CONTEXT_SWITCH_TIME = 3

# Initialize grand totals
grand_total_deadline_misses = 0
grand_total_preemptions = 0
grand_total_data_transfers = 0

# Log per-taskset results
summary_log = []

missed_priorities_log = []

for taskset_id, taskset_ in enumerate(tasksML):
    unarrived_tasks = taskset_.copy()
    taskset_size = len(unarrived_tasks)
    current_time = 0
    preemptions = 0
    deadline_misses = 0
    data_transfer_count = 0
    busy_time = 0
    completed_tasks = []
    missed_priorities = []
    deadline_miss_times = []  # Track when deadline misses occur

    # Initialize task attributes if not present
    for task in unarrived_tasks:
        if not hasattr(task, 'laxity'):
            task.laxity = task.deadline - task.burst_time

    prange = max((task.priority for task in unarrived_tasks), default=0)

    tasks = []
    cores = [None] * NUM_CORES

    print(f"\nEvaluating Taskset #{taskset_id} with Relaxation")
    print(" t  1  |  2")
    print("------|---")

    for current_time in range(SIMULATION_TIME):
        # Move arriving tasks to the ready queue
        for task in unarrived_tasks[:]:
            if task.arrival_time == current_time:
                heapq.heappush(tasks, task)
                data_transfer_count += 1
                unarrived_tasks.remove(task)

        # Assign tasks to free cores
        for core in range(NUM_CORES):
            if cores[core] is None and tasks:
                cores[core] = heapq.heappop(tasks)
                data_transfer_count += 1

        # Remove tasks with negative laxity
        for task in tasks[:]:
            if task.update_laxity() < 0:
                missed_priorities.append(task.priority)
                tasks.remove(task)
                heapq.heapify(tasks)
                data_transfer_count += 1

        # Apply relaxation and check for preemption
        if tasks:
            task = tasks[0]
            task.update_relaxation()

            for core in range(NUM_CORES):
                if cores[core] is None:
                    cores[core] = heapq.heappop(tasks)
                    data_transfer_count += 1
                    break

            worst_core = None
            max_remaining_time = -1
            for core in range(NUM_CORES):
                if cores[core] is not None and cores[core].remaining_time > max_remaining_time:
                    max_remaining_time = cores[core].remaining_time
                    worst_core = core

            if (worst_core is not None and task.update_laxity() < cores[worst_core].remaining_time
                and task.laxity >= 0):
                task_out = cores[worst_core]
                task_in = heapq.heappop(tasks)
                cores[worst_core] = task_in
                heapq.heappush(tasks, task_out)
                preemptions += 1
                data_transfer_count += 2
                cores[worst_core].remaining_time += CONTEXT_SWITCH_TIME

        # Process tasks on cores
        for core in range(NUM_CORES):
            if cores[core] is not None:
                cores[core].remaining_time -= 1
                busy_time += 1

                if cores[core].remaining_time <= 0:
                    cores[core].completion_time = current_time
                    completed_tasks.append(cores[core])

                    if cores[core].completion_time > cores[core].deadline:
                        deadline_misses += 1
                        deadline_miss_times.append(current_time)
                        missed_priorities.append(cores[core].priority)

                    cores[core] = None

        # Print core status
        core_status = [str(cores[i].id) if cores[i] else "-" for i in range(NUM_CORES)]
        print(f"{current_time}  {core_status[0]}  |  {core_status[1]}")

    # Check for incomplete tasks (missed deadlines)
    for task in tasks:
        if task.remaining_time > 0:
            deadline_misses += 1
            deadline_miss_times.append(current_time)
            missed_priorities.append(task.priority)
            print(f"⚠️ Task {task.id} did not complete and missed its deadline.")

    # Calculate MTBF
    if deadline_misses > 1:
        intervals = [deadline_miss_times[i+1] - deadline_miss_times[i]
                     for i in range(len(deadline_miss_times)-1)]
        mtbf = sum(intervals) / len(intervals)
    elif deadline_misses == 1:
        mtbf = SIMULATION_TIME  # Only one failure, so MTBF is full simulation time
    else:
        mtbf = float('1000')     # No failures

    print(f"\nTotal Preemptions: {preemptions}")
    print(f"Total Deadline Misses: {deadline_misses}")
    print(f"CPU Utilization: {(busy_time / (SIMULATION_TIME * NUM_CORES)) * 100:.2f}%")
    print(f"MTBF (Deadline Misses): {mtbf:.2f} cycles")

    # Update grand totals
    grand_total_deadline_misses += deadline_misses
    grand_total_preemptions += preemptions
    grand_total_data_transfers += data_transfer_count
    taskset_utilization = (busy_time / (SIMULATION_TIME * NUM_CORES)) * 100

    summary_log.append([
        taskset_id,
        preemptions,
        deadline_misses,
        data_transfer_count,
        f"{taskset_utilization:.2f}",
        ','.join(str(p) for p in missed_priorities),
        f"{mtbf:.2f}"
    ])

# Save to CSV with missed priorities and MTBF
with open('../relax_taskset_summary.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Taskset_ID', 'Preemptions', 'Deadline_Misses', 'Data_Transfers', 'CPU_Utilization(%)', 'Missed_Task_Priorities', 'MTBF_Cycles'])
    writer.writerows(summary_log)

print("\n✅ Saved relaxation taskset summaries with missed priorities and MTBF to 'relax_taskset_summary.csv'")
