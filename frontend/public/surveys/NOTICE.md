# Vendored HMI surveys

The HTML questionnaires in this folder come from the **hmisurveys** project by
Clark Borst (Delft University of Technology, Control & Simulation), available at
<https://github.com/AI4REALNET/hmisurveys> and licensed under **GPL-3.0** (see
`LICENSE` next to this file). They keep that license here — the MPL-2.0 of the
rest of InteractiveAI does not apply to them.

Only the files used by the chain are vendored:

| File | Origin in hmisurveys |
| --- | --- |
| `surveychainer.html` | `html/surveychainer.html` |
| `understanding/understanding.html` | `html/understanding/understanding.html` |
| `experience/ueq_short.html` | `html/experience/ueq_short.html` |
| `acceptance/vanderlaan.html` | `html/acceptance/vanderlaan.html` |
| `workload/mch.html` | `html/workload/mch.html` |

## Modifications

Made so the chain can be embedded in InteractiveAI, and kept as small as
possible so an upstream update stays easy to re-apply:

1. **Every questionnaire** posts its answers to `window.parent` instead of
   `window.top`. The chainer is itself inside an InteractiveAI iframe, so
   `window.top` is the application shell and the chainer would never see the
   answers.
2. **`surveychainer.html`** reads `?participant=` and `?condition=` from its
   URL. When both are present the Participant/Condition form is prefilled and
   hidden — InteractiveAI passes the trace session id and the use case, so the
   operator only presses *Start*. Without them the chainer behaves as before and
   asks for both.
3. **`surveychainer.html`** selects its questionnaires from `CHAINS[condition]`,
   falling back to `DEFAULT_CHAIN`, so a use case can get its own chain.
4. **`surveychainer.html`** lays its page out with flexbox so it fills the frame
   it is given instead of assuming a full browser window (`height: 80vh`).
