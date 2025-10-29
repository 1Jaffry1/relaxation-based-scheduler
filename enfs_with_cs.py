### FINAL

import numpy as np
import copy
import csv

from nuscenes_ttc.ENFS import nsga2

CONTEXT_SWITCH_TIME = 1  # in clock cycles
NUM_CORES = 2

# --- Data Structures ---

# Add preemption tracking to the Task class
class Task:
    def __init__(self, id, arrival_time, burst_time, deadline, priority):
        self.id = id
        self.arrival_time = arrival_time
        self.burst_time = burst_time
        self.deadline = deadline
        self.priority = priority
        self.start_time = None
        self.finish_time = None
        self.assigned_core = None
        self.remaining_time = burst_time
        self.wcet = burst_time  # For emergency criterion
        self.completion_time = None  # Track when the task is completed
        self.preemptions = 0  # Track the number of preemptions

# Modify the scheduling loop to support preemption
def enf_s_simulation(tasksets, fnn, num_cores=NUM_CORES, simulation_time=1000):
    summary_log = []
    missed_priorities_log = []
    taskset_id = 0

    for taskset_ in tasksets:
        taskset_id += 1
        completed_tasks = []
        missed_priorities = []
        deadline_miss_times = []
        busy_time = 0
        taskset_size = len(taskset_)
        cores = [Core(i) for i in range(num_cores)]
        core_tasks = [None] * num_cores
        time = 0
        tasks = copy.deepcopy(taskset_)
        completed_ids = set()
        scheduled = set()
        preemptions = 0  # Track total preemptions

        while len(completed_ids) < len(tasks):
            ready_list = [t for t in tasks if t.id not in scheduled and t.arrival_time <= time]
            if not ready_list:
                time += 1
                continue

            sorted_ready = sort_ready_list_by_emergency(ready_list, max(t.deadline for t in tasks))
            for core_id in range(num_cores):
                running_task = core_tasks[core_id]
                if running_task:
                    # Check if the running task should be preempted
                    best_task = sorted_ready[0]
                    if best_task.priority > running_task.priority:
                        # Preempt the running task
                        running_task.preemptions += 1
                        preemptions += 1
                        core_tasks[core_id] = best_task
                        scheduled.add(best_task.id)
                        sorted_ready.remove(best_task)
                elif sorted_ready:
                    # Assign a new task to the idle core
                    best_task = sorted_ready.pop(0)
                    core_tasks[core_id] = best_task
                    scheduled.add(best_task.id)

            # Update remaining time for running tasks
            for core_id in range(num_cores):
                task = core_tasks[core_id]
                if task:
                    task.remaining_time -= 1
                    if task.remaining_time <= 0:
                        completed_tasks.append(task)
                        completed_ids.add(task.id)
                        core_tasks[core_id] = None

            time += 1

        # Log preemptions in the summary
        summary_log.append([
            taskset_id,
            taskset_size,
            preemptions,  # Log preemptions
            len(missed_priorities),
            0,  # Data transfers (not tracked in ENF-S)
            f"{(busy_time / (simulation_time * num_cores)) * 100:.2f}",
            max(t.finish_time for t in completed_tasks) if completed_tasks else 0
        ])

class Core:
    def __init__(self, id):
        self.id = id
        self.available_time = 0
        self.total_busy_time = 0

# --- Fuzzy Neural Network ---

def fuzzify(value, bounds):
    low, mid, high = bounds
    if value < low:
        return [1.0, 0.0, 0.0]
    elif value < mid:
        return [(mid - value) / (mid - low), (value - low) / (mid - low), 0.0]
    elif value < high:
        return [0.0, (high - value) / (high - mid), (value - mid) / (high - mid)]
    else:
        return [0.0, 0.0, 1.0]

class FNN:
    def __init__(self, rule_weights):
        self.rule_weights = rule_weights  # 243 weights (3^5 for 5 inputs)

    def evaluate(self, core_util, task_priority, deadline_tightness, core_reliability, core_mtbf):
        util_mf = fuzzify(core_util, (0, 0.5, 1.0))
        prio_mf = fuzzify(task_priority, (1, 2, 3))
        tight_mf = fuzzify(deadline_tightness, (0, 0.5, 1.0))
        rel_mf = fuzzify(core_reliability, (0.95, 0.98, 1.0))
        mtbf_mf = fuzzify(core_mtbf, (0, 10, 100))
        outputs = []
        idx = 0
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    for l in range(3):
                        for m in range(3):
                            firing_strength = util_mf[i] * prio_mf[j] * tight_mf[k] * rel_mf[l] * mtbf_mf[m]
                            outputs.append(firing_strength * self.rule_weights[idx])
                            idx += 1
        total_strength = sum([util_mf[i//81]*prio_mf[(i//27)%3]*tight_mf[(i//9)%3]*rel_mf[(i//3)%3]*mtbf_mf[i%3] for i in range(243)])
        if total_strength == 0:
            return 1e6
        return sum(outputs) / total_strength

# --- Reliability and MTBF ---

def calc_reliability(core):
    util = min(1.0, core.total_busy_time / (core.available_time if core.available_time > 0 else 1))
    k = 0.05
    reliability = np.exp(-k * util)
    return reliability

def calc_failure_rate(core):
    util = min(1.0, core.total_busy_time / (core.available_time if core.available_time > 0 else 1))
    k = 0.05
    return k * util + 1e-6

def calc_mtbf(core):
    return 1.0 / calc_failure_rate(core)

def system_mtbf(cores):
    total_failure_rate = sum(calc_failure_rate(core) for core in cores)

    if total_failure_rate > 0:
        return 1.0 / total_failure_rate
    else:
        avg=0
        for core in cores:
            avg+=core.total_busy_time
        return avg/len(cores)



# --- Emergency Criterion and Ready List ---

def sort_ready_list_by_emergency(ready_list, app_deadline):
    # Lower (DApp - WCET) is more urgent
    return sorted(ready_list, key=lambda t: app_deadline - t.burst_time)

# --- Simulation and Evaluation ---

def enf_s_simulation(tasksets, fnn, num_cores=NUM_CORES, simulation_time=1000):
    summary_log = []  # Collect all taskset summaries here
    missed_priorities_log = []  # Collect missed priorities for each taskset
    taskset_id = 0

    for taskset_ in tasksets:
        taskset_id += 1
        completed_tasks = []
        missed_priorities = []
        deadline_miss_times = []
        busy_time = 0
        taskset_size = len(taskset_)
        cores = [Core(i) for i in range(num_cores)]
        core_tasks = [None] * num_cores
        time = 0
        tasks = copy.deepcopy(taskset_)
        completed_ids = set()
        scheduled = set()
        wcrt = 0  # Initialize WCRT
        app_deadline = max(t.deadline for t in tasks)

        print(f"\n🔵 ENF-S: Taskset #{taskset_id}\nt  1  |  2\n------|---")

        print(f"\n🔵 ENF-S: Taskset #{taskset_id}")
        print("t  1  |  2")
        print("------|---")

        while len(completed_ids) < len(tasks):
            ready_list = [t for t in tasks if t.id not in scheduled and t.arrival_time <= time]
            core_status = [str(core_tasks[i].id) if core_tasks[i] else "-" for i in range(num_cores)]

            # Print the status for the current second
            print(f"{time}  {core_status[0]}  |  {core_status[1]}")

            if not ready_list:
                # Reduce remaining time for running tasks
                for core_id in range(num_cores):
                    task = core_tasks[core_id]
                    if task:
                        task.remaining_time -= 1
                        if task.remaining_time <= 0:
                            completed_tasks.append(task)
                            completed_ids.add(task.id)
                            core_tasks[core_id] = None
                time += 1
                continue

            sorted_ready = sort_ready_list_by_emergency(ready_list, app_deadline)
            for core_id in range(num_cores):
                if core_tasks[core_id] is None:
                    # Core is idle, assign a new task
                    best_task = None
                    best_score = float('inf')
                    for task in sorted_ready:
                        if task.id in scheduled:
                            continue
                        core_util = 0 if time == 0 else busy_time / (time * num_cores)
                        prio_norm = task.priority / 3
                        tightness = max(0.0,
                                        min(1.0, (task.deadline - (time + task.burst_time)) / max(1, task.deadline)))
                        reliability = calc_reliability(cores[core_id])
                        mtbf = calc_mtbf(cores[core_id])
                        score = fnn.evaluate(core_util, prio_norm, tightness, reliability, mtbf)
                        if score < best_score:
                            best_score = score
                            best_task = task

                    if best_task:
                        best_task.start_time = time + CONTEXT_SWITCH_TIME
                        best_task.finish_time = best_task.start_time + best_task.remaining_time
                        best_task.assigned_core = core_id
                        core_tasks[core_id] = best_task
                        cores[core_id].available_time = best_task.finish_time
                        cores[core_id].total_busy_time += best_task.remaining_time
                        busy_time += best_task.remaining_time
                        scheduled.add(best_task.id)

            # Reduce remaining time for running tasks
            for core_id in range(num_cores):
                task = core_tasks[core_id]
                if task:
                    task.remaining_time -= 1
                    if task.remaining_time <= 0:
                        task.finish_time = time  # Record the finish time
                        if task.finish_time > task.deadline:
                            missed_priorities.append(task.priority)
                            deadline_miss_times.append(task.finish_time)
                        completed_tasks.append(task)
                        completed_ids.add(task.id)
                        core_tasks[core_id] = None

            time += 1

        for task in tasks:
            if task.id not in completed_ids:
                missed_priorities.append(getattr(task, 'priority', 'N/A'))
                deadline_miss_times.append(time)

        deadline_misses = len(missed_priorities)
        makespan = max(t.finish_time for t in completed_tasks) if completed_tasks else 0
        mtbf = makespan/(deadline_misses+1)

        taskset_utilization = (busy_time / (simulation_time * num_cores)) * 100

        print("\n🎯 Completion Summary:")
        for task in completed_tasks:
            if task.finish_time > task.deadline:
                print(f"❌ MISS: Task {task.id} completed at {task.finish_time} after deadline {task.deadline}")
            else:
                print(f"✅ DONE: Task {task.id} completed at {task.finish_time} before deadline {task.deadline}")

        print(f"\n📈 Total Deadline Misses: {deadline_misses}")
        print(f"⚡ CPU Utilization: {taskset_utilization:.2f}%")
        print(f"⏱️ Makespan: {makespan} cycles")
        print(f"📊 MTBF: {mtbf:.2f} cycles")

        summary_log.append([
            taskset_id,
            taskset_size,
            0,  # Preemptions (not tracked in ENF-S)
            deadline_misses,
            0,  # Data transfers (not tracked in ENF-S)
            f"{taskset_utilization:.2f}",
            makespan,
            wcrt,
            mtbf
        ])
        missed_priorities_log.append((taskset_id, missed_priorities))

    # Write all taskset summaries to a single file
    with open('enfs_taskset_summary.csv', 'w', newline='') as f:
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

    print("\n✅ Saved ENF-S taskset summaries with missed priorities to 'enfs_taskset_summary.csv'")


import os
import pickle

# --- Training Phase ---
def train_and_save_model(tasksets, filename, pop_size=50, generations=50):
    """
    Train the model using NSGA-II and save it to a file.
    """
    if not os.path.exists(filename):
        print("Training FNN with NSGA-II (this may take a minute)...")
        trained_fnn = nsga2(tasksets, pop_size=pop_size, generations=generations)
        with open(filename, 'wb') as f:
            pickle.dump(trained_fnn, f)
        print(f"Training complete. Model saved to {filename}.")
    else:
        print(f"Model already exists at {filename}. Skipping training.")

# --- Scheduling Phase ---
def load_model(filename):
    """
    Load the trained model from a file.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Trained model file '{filename}' not found. Please train the model first.")
    with open(filename, 'rb') as f:
        return pickle.load(f)

# --- Example Usage ---
if __name__ == "__main__":
    from random_taskset_for_training import tasks as train
    from aperiodic_task_sets import tasks as test

    model_file = "trained_fnn.pkl"

    # Train and save the model (if not already trained)
    train_and_save_model(train, model_file)

    # Load the trained model
    trained_fnn = load_model(model_file)

    # Run the simulation with the trained model
    enf_s_simulation(test, trained_fnn, num_cores=NUM_CORES, simulation_time=1000)