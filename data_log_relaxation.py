import heapq
import csv
from random_taskset import tasks

epsilon = 1e-9
NUM_CORES = 2
ALPHA = 0.6
BETA = 0.4
GAMMA = 0
CONTEXT_SWITCH_TIME = 3
current_time = 0
preemptions = 0
deadline_misses = 0
history = []
prange = 0
data_transfer_count = 0
training_log = []

# import taskset
from ML.taskset import SIMULATION_TIME, log_results

taskset_id = -1  # Taskset counter

for taskset_ in tasks:
    taskset_id += 1
    unarrived_tasks = taskset_
    taskset_size = len(unarrived_tasks)
    current_time = 0
    preemptions = 0
    deadline_misses = 0
    history = []
    data_transfer_count = 0

    for task in unarrived_tasks:
        if not hasattr(task, 'laxity'):
            task.laxity = task.deadline - task.burst_time
        if task.priority > prange:
            prange = task.priority

    tasks = []
    completed_tasks = []

    cores = [None] * NUM_CORES

    print(f"{taskset_id}, RELAX\n t  1  |  2\n------|---")
    for current_time in range(SIMULATION_TIME):
        for task in unarrived_tasks:
            if task.arrival_time == current_time:
                heapq.heappush(tasks, task)
                data_transfer_count += 1

        unarrived_tasks = [task for task in unarrived_tasks if task.arrival_time > current_time]

        for core in range(len(cores)):
            if cores[core] is None and tasks:
                cores[core] = heapq.heappop(tasks)
                assigned_core_id = core
                preemption_flag = 0
                training_log.append([
                    taskset_id,
                    cores[core].id, current_time, cores[core].remaining_time, cores[core].deadline,
                    getattr(cores[core], 'priority', 0), getattr(cores[core], 'laxity', 0),
                    assigned_core_id, preemption_flag
                ])
                data_transfer_count += 1

        for task in tasks[:]:
            if task.update_laxity() < 0:
                tasks.remove(task)
                heapq.heapify(tasks)
                data_transfer_count += 1

        if tasks:
            task = tasks[0]
            task.update_relaxation()

            for core in range(len(cores)):
                if cores[core] is None:
                    cores[core] = heapq.heappop(tasks)
                    assigned_core_id = core
                    preemption_flag = 0
                    training_log.append([
                        taskset_id,
                        cores[core].id, current_time, cores[core].remaining_time, cores[core].deadline,
                        getattr(cores[core], 'priority', 0), getattr(cores[core], 'laxity', 0),
                        assigned_core_id, preemption_flag
                    ])
                    data_transfer_count += 1
                    break

            worst_core = None
            max_remaining_time = -1
            for core in range(len(cores)):
                if cores[core] is not None and cores[core].remaining_time > max_remaining_time:
                    max_remaining_time = cores[core].remaining_time
                    worst_core = core

            if worst_core is not None and task.update_laxity() < cores[worst_core].remaining_time and task.laxity >= 0:
                task_out = cores[worst_core]
                task_in = heapq.heappop(tasks)
                cores[worst_core] = task_in
                heapq.heappush(tasks, task_out)
                preemptions += 1
                data_transfer_count += 2
                cores[worst_core].remaining_time += CONTEXT_SWITCH_TIME
                history.append(f"Time {current_time}: Task {task_in.id} (Laxity: {task_in.laxity}) preempted task {task_out.id} (Remaining time: {task_out.remaining_time}) on Core {worst_core}.")
                assigned_core_id = worst_core
                preemption_flag = 1
                training_log.append([
                    taskset_id,
                    task_in.id, current_time, task_in.remaining_time, task_in.deadline,
                    getattr(task_in, 'priority', 0), getattr(task_in, 'laxity', 0),
                    assigned_core_id, preemption_flag
                ])

        for core in range(len(cores)):
            if cores[core] is not None:
                cores[core].remaining_time -= 1
                if cores[core].remaining_time <= 0:
                    cores[core].completion_time = current_time
                    completed_tasks.append(cores[core])
                    if current_time > cores[core].deadline:
                        deadline_misses += 1
                    cores[core] = None

        core_status = [str(cores[i].id) if cores[i] else "-" for i in range(NUM_CORES)]
        print(f"{current_time}  {core_status[0]}  |  {core_status[1]}")

    for task in tasks:
        if task.remaining_time > 0:
            deadline_misses += 1
            print(f"Task {task.id} did not complete and missed its deadline.")

    print("\nHistory of preemptions:")
    for event in history:
        print(event)

    print("\nCompletion times and deadlines:")
    for task in completed_tasks:
        if task.completion_time > task.deadline:
            print(f"MISS: Task {task.id} completed at time {task.completion_time} and missed its deadline at {task.deadline}.")
        else:
            print(f"COMPLETION: Task {task.id} completed at time {task.completion_time} with deadline {task.deadline}")
    for task in tasks:
        if task.completion_time is None:
            print(f"NOT COMPLETE: Task {task.id} did not complete and missed its deadline.")

    print(f"\nTotal preemptions: {preemptions}")
    print(f"Total deadline misses: {deadline_misses}")
    print(f"Total data transfers: {data_transfer_count}")

    log_results('relaxation', taskset_size, preemptions, deadline_misses, data_transfer_count)

# Save training log after all tasksets
with open('../relaxation_training_data.csv', 'w', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(['taskset_id', 'task_id', 'time', 'remaining_time', 'deadline', 'priority', 'laxity', 'core_id', 'preempted'])
    for entry in training_log:
        writer.writerow(entry)
