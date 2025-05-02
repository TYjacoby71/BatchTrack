
# BatchTrack MVP Bug & QA Checklist

## 1. UNIVERSAL STOCK CHECK SERVICE (USCS)

- [ ] Global `/api/check-stock` endpoint implemented
- [ ] Accepts recipe_id, scale, container plan
- [ ] Returns unified list with type, name, needed, available, status
- [ ] Scaling calculations verified
- [ ] Unit conversion integration complete
- [ ] Container validation working
- [ ] Status indicators (OK/LOW/NEEDED) accurate
- [ ] Containment failure detection working
- [ ] Override option implemented
- [ ] Error handling with clear messages

## 2. PLAN PRODUCTION FLOW

- [ ] Scale selection shown first
- [ ] Container selection follows scale input
- [ ] Strict Mode (Auto Fill) default ON
- [ ] Recipe yield predictions accurate
- [ ] Flexible Mode container selection working
- [ ] Auto-fill container logic verified
- [ ] Container type filtering working
- [ ] Progress bar shows containment %
- [ ] Remaining volume display accurate
- [ ] Manual container adjustments possible
- [ ] Containment error handling working
- [ ] Yield predictions visible in Flex Mode

## 3. CONTAINER MANAGEMENT

- [ ] Container model complete (Name/Amount/Unit)
- [ ] Volume vs Count logic working
- [ ] Count-based multiplication correct
- [ ] Volume-based capacity correct
- [ ] Quick Add Modal in Recipe Edit
- [ ] Container validation complete

## 4. RECIPE MANAGEMENT

- [ ] Predicted Yield field required
- [ ] Yield Unit type enforced
- [ ] Container eligibility working
- [ ] Quick Add Container attachment working

## 5. BATCH COMPLETION

- [ ] Actual Yield recording
- [ ] Yield comparison working
- [ ] Recipe update option available
- [ ] Variation creation option working

## PRIORITY ORDER

1. 🔴 Universal Stock Check Service
2. 🟡 Plan Production Setup
3. 🟢 Container Quick Add Modal
4. 🟢 Container System Revamp
5. 🟢 Batch Completion Flow

## Current Issues

1. Stock check endpoint needs centralization
2. Container validation incomplete
3. Yield calculations need verification
4. Mobile optimization needed
5. Error message standardization required
