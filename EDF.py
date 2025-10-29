import heapq
import csv

epsilon = 1e-9
NUM_CORES = 2
CONTEXT_SWITCH_TIME = 1

# Import the Task class used by the external task list
from taskset import Task
from aperiodic_task_sets import tasks as tasks
from taskset import SIMULATION_TIME

# --- Monkey patch __lt__ into the original Task class ---
def task_lt(self, other):
    return (self.deadline, self.id) < (other.deadline, other.id)

Task.__lt__ = task_lt  # This affects all instances globally

# Optional: patch __repr__ for better print formatting
def task_repr(self):
    return f'Task: {self.id}, DL: {self.deadline}, remaining: {self.remaining_time},'

Task.__repr__ = task_repr


# --- Global Totals ---
grand_total_deadline_misses = 0
grand_total_preemptions = 0
grand_total_data_transfers = 0
summary_log = []
missed_priorities_log = []

taskset_id = -1

for taskset_ in tasks:
    taskset_id += 1
    unarrived_tasks = taskset_
    taskset_size = len(unarrived_tasks)
    current_time = 0
    preemptions = 0
    deadline_misses = 0
    data_transfer_count = 0
    busy_time = 0
    wcrt = 0  # Worst-case response time (completion - arrival) for this taskset
    history = []

    tasks = []
    completed_tasks = []
    missed_priorities = []
    deadline_miss_times = []

    cores = [None] * NUM_CORES

    print(f"\n🔵 EDF: Taskset #{taskset_id}\nt  1  |  2\n------|---")

    for current_time in range(SIMULATION_TIME):
        for task in unarrived_tasks:
            if task.arrival_time == current_time:
                heapq.heappush(tasks, task)
                data_transfer_count += 1

        unarrived_tasks = [task for task in unarrived_tasks if task.arrival_time > current_time]

        for core in range(NUM_CORES):
            if cores[core] is None and tasks:
                task_in = heapq.heappop(tasks)
                # Do NOT add CONTEXT_SWITCH_TIME here; core was idle
                cores[core] = task_in
                data_transfer_count += 1
                # Optional: log
                # history.append(f"Time {current_time}: Task {task_in.id} started on idle Core {core}")

        # 2) Consider preemption only if there are still tasks waiting AND all cores are busy
        if tasks and all(cores[c] is not None for c in range(NUM_CORES)):
            incoming = tasks[0]  # peek the earliest-deadline waiting task (heap head)

            # Find the running task with the LATEST deadline (least urgent)
            worst_core = max(range(NUM_CORES), key=lambda c: cores[c].deadline)
            running = cores[worst_core]

            # Preempt only if incoming is more urgent (earlier deadline)
            if incoming.deadline < running.deadline:
                # Evict the less-urgent running task and load the incoming one
                task_out = running
                task_in = heapq.heappop(tasks)

                # Charge context-switch cost ONLY for a true preemption load
                task_in.remaining_time += CONTEXT_SWITCH_TIME

                # If your model charges save+load, also do:
                task_out.remaining_time += CONTEXT_SWITCH_TIME

                cores[worst_core] = task_in
                heapq.heappush(tasks, task_out)

                preemptions += 1
                data_transfer_count += 2  # out + in transfers

                history.append(
                    f"Time {current_time}: Task {task_in.id} (Deadline: {task_in.deadline}) "
                    f"preempted Task {task_out.id} (Deadline: {task_out.deadline}) on Core {worst_core}"
                )
        for core in range(NUM_CORES):
            if cores[core] is not None:
                cores[core].remaining_time -= 1
                busy_time += 1

                if cores[core].remaining_time <= 0:
                    cores[core].completion_time = current_time
                    # Update WCRT upon completion
                    try:
                        rt = cores[core].completion_time - cores[core].arrival_time
                        if rt > wcrt:
                            wcrt = rt
                    except Exception:
                        pass
                    completed_tasks.append(cores[core])

                    if cores[core].completion_time > cores[core].deadline + cores[core].arrival_time:
                        deadline_misses += 1
                        missed_priorities.append(getattr(cores[core], 'priority', 'N/A'))
                        deadline_miss_times.append(current_time)

                    cores[core] = None

        core_status = [str(cores[i].id) if cores[i] else "-" for i in range(NUM_CORES)]
        print(f"{current_time}  {core_status[0]}  |  {core_status[1]}")

    # Final Sweep for Missed Tasks
    for t in tasks:
        if t.remaining_time > 0:
            deadline_misses += 1
            deadline_miss_times.append(makespan)
            missed_priorities.append(t.priority)  # Log missed priority


    if completed_tasks:
        makespan = max(task.completion_time for task in completed_tasks)
    else:
        makespan = 0

    # Calculate MTBF
    mtbf = makespan / (deadline_misses + 1)

    print("\n📜 Preemption History:")
    for event in history:
        print(event)

    print("\n🎯 Completion Summary:")
    for task in completed_tasks:
        if task.completion_time > task.deadline:
            print(f"❌ MISS: Task {task.id} completed at {task.completion_time} after deadline {task.deadline}")
        else:
            print(f"✅ DONE: Task {task.id} completed at {task.completion_time} before deadline {task.deadline}")

    print(f"\n📈 Total Preemptions: {preemptions}")
    print(f"💥 Total Deadline Misses: {deadline_misses}")
    print(f"🔄 Total Data Transfers: {data_transfer_count}")
    print(f"⏱️ Makespan: {makespan} cycles")
    print(f"📊 MTBF: {mtbf:.2f} cycles")

    taskset_utilization = (busy_time / (SIMULATION_TIME * NUM_CORES)) * 100
    print(f"⚡ CPU Utilization for this taskset: {taskset_utilization:.2f}%")

    grand_total_deadline_misses += deadline_misses
    grand_total_preemptions += preemptions
    grand_total_data_transfers += data_transfer_count

    summary_log.append([
        taskset_id,
        taskset_size,
        preemptions,
        deadline_misses,
        data_transfer_count,
        f"{taskset_utilization:.2f}",
        makespan,
        wcrt,
        mtbf
    ])
    missed_priorities_log.append((taskset_id, missed_priorities))

print("\n🚀 Final Grand Totals for EDF:")
print(f"💥 Grand Total Deadline Misses: {grand_total_deadline_misses}")
print(f"🔄 Grand Total Preemptions: {grand_total_preemptions}")
print(f"🔁 Grand Total Data Transfers: {grand_total_data_transfers}")
print(f"⚡ Overall CPU Utilization: {taskset_utilization:.2f}%")

print("\n🧾 Priorities of Missed Deadline Tasks (per Taskset):")
for tid, plist in missed_priorities_log:
    print(f"Taskset {tid}: Missed Priorities -> {plist}")

with open('edf_taskset_summary.csv', 'w', newline='') as f:
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

print("\n✅ Saved EDF taskset summaries with missed priorities, MTBF, and makespan to 'edf_taskset_summary.csv'")