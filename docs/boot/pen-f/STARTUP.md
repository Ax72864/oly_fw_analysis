# Startup structure

Addresses here refer to PEN-F build 3101. Execution begins at the downloaded
main image's entry, `60021020`. Reset-ROM execution and the selection of that
entry are not present in the available trace.

## Main and startup tasks

The program initializes RAM and internal helper code, configures the RTOS and
starts work on three CPU cores. These are RTOS tasks sharing memory, not Unix
processes. Only task 1 is selected by the reviewed initial auto-start enumeration.
Other compiled task descriptors reserve IDs without immediately running them.

`USTART1` is the firmware's name for startup task 47, entry `601a70cc`. Starting
it makes it schedulable; it does not mean that the camera is fully initialized.
The main initializer and peer-core tasks can continue while it runs or waits.

```text
main entry and RTOS initialization
  ├─ CPU0 system services and startup flags
  ├─ CPU1 / CPU2 initialization and interrupt-driven work
  └─ USTART1 (47)
       ├─ starts USTART3 (49)
       ├─ loads section 3 and initializes camera services
       └─ posts progress events
            USTART3 waits for readiness, starts FILECLBK and USTART4 (48)
              USTART4 loads further sections and crosses application barriers
                USTART5 (46) starts TPC (42) and FIRMUP_SRV (19)
```

The latter startup-task ordering is supported by caller execution and separate
callee probes. It is **not one uninterrupted replay through a working UI**.
Readiness words, ordinal progress values and event bitmasks have different
meanings and cannot be substituted for each other.

## Connected execution coverage

The strict main-entry replay executes native allocation, task scheduling,
interrupt handlers, section copies and peripheral setup. It reaches camera
controller initialization inside USTART1. The controller copies configuration,
registers IRQs 4–6, builds its linked structures and returns; five further
peripheral initializers also return.

The boundary is a read of `9b000000` at `602a6500`, before clearing bit 4.
At this point the SD client and later application/update tasks have not been
shown running. Section-3 data being resident does not itself prove completion
of every section constructor or use of its COLOR tables.

Major hardware assumptions in this replay are:

- Explicit ADC samples, including 415 on channel 7 for exposure-dial position A.
  This is a software threshold match, not a measured voltage.
- Scripted “Alex” serial replies and transfer completion. The firmware names
  that peripheral; its physical identity has not been established.
- Modeled storage reads from the pinned image, erased/constructed settings
  fixtures, coherent RAM aliases and scoped register readback.
- Deterministic interrupt and cross-core delivery. Native handlers and RTOS
  waits execute, but real interrupt latency and arbitrary preemption do not.
- Reviewed clock, enable and configuration registers. A successful software
  return does not establish sensor, display or ISP readiness.

## Application dispatch

Separate initialized fixtures connect BOOT-state handling to application requests.
A power wake selects shooting startup; a USB wake can select PC/USB setup;
other wake reasons select interval, power-off or Wi-Fi paths. Task 65 and the
higher-level camera state machine are therefore relevant to ordinary startup.
Those fixtures supply their entry state and cannot fill a missing main-to-entry
edge by themselves.

The ordinary startup caller survey contains no direct start of SD task 95.
Its dormant task slot remains allocated: the generic dynamic-task manager does
not accidentally reuse ID 95. Ordinary progress messages and startup-mailbox
clearing likewise do not establish a hidden SD activation.

## SD dependencies are a separate trace

A constructed recovery fixture selects task 95 and initializes its dependencies.
It executes unmount, packet cleanup and a native mount request through FILECLBK
(task 17). The mount reaches media-controller enabling, then stops at the unknown
register read `98800044` in `605a1ec3`. No successful mount or card contents are
invented at that boundary.

This demonstrates dependencies of the compiled SD client, not how holding OK
at power-on selects it. That selection may be elsewhere in main or before the
available entry; both remain possible. See [recovery](RECOVERY.md).

E-M1 II has comparable startup-task and update-service organization. Similarity
supports finding corresponding functions, but does not establish identical
pre-main recovery behavior across models.
