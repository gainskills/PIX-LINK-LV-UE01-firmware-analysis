# BA reordering log observed during Flash acquisition

During read-only capture, console messages matching `%x, flush one!` interleaved with the SPI hex output. Three long captures of the block starting0x40000 were rejected because injected messages destroyed row boundaries. No log text was silently stripped to accept those captures.

The format string is at main file offset0x18a0bc / runtime0x8018a4bc. Its reference is in the function at0x800d5a38..0x800d5ba0; disassembly is adjacent in `ba-reorder-timeout-disassembly.txt`.

Observed static behavior:

- checks entry pointer, queue count at+0x80 and saved timing value at+0x60;
- compares saved value plus10/20 against the caller's current value; these are uncalibrated units;
- single-step path increments the entry's16-bit field at+4, masks to12 bits, then calls0x800d5210 and0x800d58f0;
- conditionally prints `flush one!`; the other timeout branch references `timeout[...] ... flush all!` in the surrounding BA/reordering string group.

This supports identifying it as a receive BA reordering timeout path. It is different from the previously located PHY relink function0x80017134. Its direct call list does not include that PHY function. It does not prove a physical Ethernet link transition, an abnormal flush rate, or the X99 root cause. Acquisition itself consumes CPU/output time and may influence timing; compare faults only after acquisition stops.

The reader now uses1 KiB requests and bounded subdivision when log injection makes a response unmappable. Corrupt words remain unknown and are separately re-read twice; no9-digit truncation is allowed. Two complete reconstructed copies must still agree. Private raw evidence remains in `recovery/private-captures/` and must not be published as configuration-free logs.
