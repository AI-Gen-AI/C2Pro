# CE-S2-010: Highlight Search - Manual Testing Checklist
**Búsqueda de Highlights - Testing Manual**

**Fecha:** 2026-01-17
**Tester:** _____________
**Build Status:** ✅ PASSED (38.84s, no TypeScript errors)
**Version:** 1.0

---

## 🎯 Pre-Testing Setup

### Environment
- [ ] Browser: Chrome/Firefox/Safari (specify: _________)
- [ ] Screen Resolution: _________
- [ ] OS: Windows/Mac/Linux (specify: _________)

### Launch Application
```bash
cd vision-matched-repo
npm run dev
```

- [ ] Application launches successfully
- [ ] Navigate to Evidence Viewer page
- [ ] Confirm at least 1 document is loaded (e.g., Contract_Final.pdf)

---

## 📋 Test Cases

### TC-001: Basic Search Flow ⭐ CRITICAL

**Priority:** HIGH
**Estimated Time:** 3 minutes

**Steps:**
1. [ ] Press `Ctrl+F` (or `Cmd+F` on Mac)
2. [ ] **Verify:** SearchBar appears with slide-in animation from top
3. [ ] **Verify:** Input field is auto-focused (cursor blinking)
4. [ ] Type "payment" in the search box
5. [ ] Wait 300ms (count to 3)
6. [ ] **Verify:** Badge shows match count (e.g., "1/2")
7. [ ] **Verify:** PDF navigates to page where first match is located
8. [ ] **Verify:** Highlight appears on PDF (yellow/green/red based on confidence)
9. [ ] **Verify:** Corresponding Entity Card in right panel scrolls into view
10. [ ] **Verify:** Entity Card has pulse animation
11. [ ] Press `Enter` key
12. [ ] **Verify:** Counter updates (e.g., "2/2")
13. [ ] **Verify:** PDF navigates to next match
14. [ ] Press `Esc` key
15. [ ] **Verify:** SearchBar closes with animation
16. [ ] **Verify:** Search is cleared (no active highlight)

**Expected Result:** All verifications pass ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-002: Debounce Functionality

**Priority:** MEDIUM
**Estimated Time:** 2 minutes

**Steps:**
1. [ ] Open search with `Ctrl+F`
2. [ ] Type "p" quickly
3. [ ] Wait 100ms
4. [ ] Type "e"
5. [ ] Wait 100ms
6. [ ] Type "n"
7. [ ] Wait 500ms (count to 5)
8. [ ] **Verify:** Search executes only ONCE (check network tab or console)
9. [ ] **Verify:** Results shown are for "pen" (not "p", not "pe")

**Expected Result:** Only 1 search execution after typing stops ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-003: Navigation Loop (Circular Navigation)

**Priority:** HIGH
**Estimated Time:** 2 minutes

**Steps:**
1. [ ] Open search and type a query with 3+ matches (e.g., "the")
2. [ ] Note the total matches (e.g., "1/5")
3. [ ] Press `Enter` twice
4. [ ] **Verify:** Counter shows "3/5"
5. [ ] Continue pressing `Enter` until you reach the last match
6. [ ] **Verify:** Counter shows "5/5"
7. [ ] Press `Enter` one more time
8. [ ] **Verify:** Counter loops back to "1/5" (circular navigation)
9. [ ] Press `Shift+Enter`
10. [ ] **Verify:** Counter goes back to "5/5" (reverse loop)

**Expected Result:** Navigation loops correctly in both directions ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-004: No Matches Found

**Priority:** MEDIUM
**Estimated Time:** 1 minute

**Steps:**
1. [ ] Open search with `Ctrl+F`
2. [ ] Type "xyzabc123" (gibberish that won't match)
3. [ ] Wait for debounce (300ms)
4. [ ] **Verify:** Badge shows "No matches"
5. [ ] **Verify:** Badge has gray/muted color
6. [ ] **Verify:** Next button is disabled (grayed out)
7. [ ] **Verify:** Previous button is disabled (grayed out)
8. [ ] **Verify:** No navigation occurs in PDF
9. [ ] Clear the input and type "payment"
10. [ ] **Verify:** Matches found, buttons enabled

**Expected Result:** Graceful handling of no results ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-005: Document Switch

**Priority:** HIGH
**Estimated Time:** 3 minutes

**Steps:**
1. [ ] Ensure you're on "Contract_Final.pdf" document
2. [ ] Open search and type "penalty"
3. [ ] Note the number of matches (should be 1-2)
4. [ ] **Verify:** Matches are found
5. [ ] Using the document dropdown, switch to "Project_Schedule_v3.pdf"
6. [ ] **Verify:** Search query persists ("penalty" still in input)
7. [ ] **Verify:** Matches are recalculated for new document
8. [ ] **Verify:** Badge updates (likely "No matches" for schedule)
9. [ ] Switch back to "Contract_Final.pdf"
10. [ ] **Verify:** Original matches found again

**Expected Result:** Search adapts to document changes ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-006: Case Insensitivity

**Priority:** MEDIUM
**Estimated Time:** 2 minutes

**Steps:**
1. [ ] Open search
2. [ ] Type "PENALTY" (all uppercase)
3. [ ] **Verify:** Finds "Penalty Clause" entity (if exists)
4. [ ] Note the number of matches (e.g., 1)
5. [ ] Clear and type "penalty" (all lowercase)
6. [ ] **Verify:** Same number of matches
7. [ ] Clear and type "PeNaLtY" (mixed case)
8. [ ] **Verify:** Same number of matches

**Expected Result:** All cases find the same matches ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-007: Multi-Field Search

**Priority:** HIGH
**Estimated Time:** 4 minutes

**Prerequisite:** Know the mock data:
- Entity ENT-002: type="Payment Terms", text="Payment shall be made...", id="ENT-002"

**Steps:**

**Test 7.1: Search by Type**
1. [ ] Open search
2. [ ] Type "payment terms"
3. [ ] **Verify:** Finds entity with type "Payment Terms"
4. [ ] **Verify:** Badge shows "1/X"

**Test 7.2: Search by Text Content**
5. [ ] Clear and type "shall be made"
6. [ ] **Verify:** Finds same entity (searches in text field)

**Test 7.3: Search by Entity ID**
7. [ ] Clear and type "ENT-002"
8. [ ] **Verify:** Finds entity by ID
9. [ ] **Verify:** Navigates to correct page

**Expected Result:** All 3 fields are searchable ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-008: Keyboard Shortcuts

**Priority:** CRITICAL
**Estimated Time:** 3 minutes

**Steps:**

**Test 8.1: Open Search**
1. [ ] With search closed, press `Ctrl+F` (Windows/Linux) or `Cmd+F` (Mac)
2. [ ] **Verify:** Search opens
3. [ ] **Verify:** Browser's native search does NOT open

**Test 8.2: Close Search**
4. [ ] Press `Esc`
5. [ ] **Verify:** Search closes
6. [ ] Open search again with `Ctrl+F`

**Test 8.3: Navigate with Enter**
7. [ ] Type a query with 2+ matches
8. [ ] Press `Enter`
9. [ ] **Verify:** Navigates to next match
10. [ ] Press `Enter` again
11. [ ] **Verify:** Navigates to next match

**Test 8.4: Navigate Backwards**
12. [ ] Press `Shift+Enter`
13. [ ] **Verify:** Navigates to previous match

**Test 8.5: Shortcuts Only When Active**
14. [ ] Close search with `Esc`
15. [ ] Press `Enter` (with search closed)
16. [ ] **Verify:** Nothing happens (no navigation)

**Expected Result:** All shortcuts work correctly ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-009: Performance (100+ Entities) 🚀

**Priority:** LOW (Optional)
**Estimated Time:** 5 minutes

**Note:** This test requires modifying mock data to have 100+ entities. Skip if not critical.

**Steps:**
1. [ ] (Setup) Duplicate mock entities to create 100+ total
2. [ ] Open search
3. [ ] Type a common word that matches 50+ entities (e.g., "the")
4. [ ] Start a timer
5. [ ] Wait for results to appear
6. [ ] Stop timer
7. [ ] **Verify:** Results appear within 500ms
8. [ ] **Verify:** No UI freeze or lag
9. [ ] Navigate through results with `Enter`
10. [ ] **Verify:** Navigation is smooth (no stuttering)

**Expected Result:** Performance is acceptable with large datasets ✅

**Actual Result:** Time to results: _____ ms

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

### TC-010: Accessibility (Keyboard Only) ♿

**Priority:** MEDIUM
**Estimated Time:** 3 minutes

**Steps:**

**Test 10.1: Keyboard Navigation**
1. [ ] Without using mouse, open search with `Ctrl+F`
2. [ ] **Verify:** Input receives focus automatically
3. [ ] Type a query
4. [ ] Press `Tab`
5. [ ] **Verify:** Focus moves to Next button
6. [ ] Press `Tab` again
7. [ ] **Verify:** Focus moves to Previous button
8. [ ] Press `Tab` again
9. [ ] **Verify:** Focus moves to Close button

**Test 10.2: Screen Reader (if available)**
10. [ ] Enable screen reader (NVDA/JAWS/VoiceOver)
11. [ ] Open search
12. [ ] Type a query with matches
13. [ ] **Verify:** Screen reader announces match count
14. [ ] Navigate to next match
15. [ ] **Verify:** Screen reader announces current match number

**Expected Result:** Fully keyboard accessible ✅

**Actual Result:** _____________

**Pass/Fail:** [ ] PASS [ ] FAIL

**Notes/Issues:** _____________

---

## 🐛 Bug Report Template

If you find any issues during testing, use this template:

```markdown
### Bug #___

**Test Case:** TC-XXX
**Severity:** Critical / High / Medium / Low
**Browser:** Chrome/Firefox/Safari
**OS:** Windows/Mac/Linux

**Steps to Reproduce:**
1.
2.
3.

**Expected Result:**


**Actual Result:**


**Screenshots/Video:**
[Attach if available]

**Console Errors:**
[Paste any errors from browser console]

**Additional Notes:**

```

---

## 📊 Test Summary

Fill this out after completing all tests:

| Test Case | Status | Time | Notes |
|-----------|--------|------|-------|
| TC-001: Basic Search Flow | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-002: Debounce | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-003: Navigation Loop | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-004: No Matches | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-005: Document Switch | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-006: Case Insensitivity | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-007: Multi-Field Search | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-008: Keyboard Shortcuts | [ ] PASS [ ] FAIL | _____ | _____ |
| TC-009: Performance (Optional) | [ ] PASS [ ] FAIL [ ] SKIP | _____ | _____ |
| TC-010: Accessibility | [ ] PASS [ ] FAIL | _____ | _____ |

**Total Tests Run:** ___ / 10
**Passed:** ___
**Failed:** ___
**Skipped:** ___

**Overall Result:** [ ] PASS [ ] FAIL

**Tested By:** _______________
**Date:** _______________
**Build Version:** _______________

---

## ✅ Sign-off

### Tester Sign-off
I confirm that I have executed the above test cases and documented the results accurately.

**Signature:** _______________
**Date:** _______________

### Developer Sign-off
I acknowledge the test results and will address any issues found.

**Signature:** _______________
**Date:** _______________

---

## 📝 Additional Notes

Use this space for any additional observations, suggestions, or concerns:

```
[Your notes here]
```

---

## 🔄 Regression Testing

If bugs are found and fixed, re-run the failed test cases:

**Re-test Date:** _______________

| Test Case | Original Status | Retest Status |
|-----------|-----------------|---------------|
| TC-XXX | FAIL | [ ] PASS [ ] FAIL |
| TC-XXX | FAIL | [ ] PASS [ ] FAIL |

---

**Document Version:** 1.0
**Last Updated:** 2026-01-17
**Prepared By:** Claude Code


---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Added metadata block during repository-wide docs format pass.
