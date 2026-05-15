# Demo Troubleshooting — Quick Reference

For full operator narrative see `demo/README.md`. These are the top five
recovery steps.

1. **Agent loops or doesn't terminate.** Click "Reset conversation" in the
   sidebar. Reload the same scenario.
2. **HITL banner fires unexpectedly.** Tell the audience: *"This is the
   system's safety net — in production this routes to a human agent in under
   30 seconds."* Then proceed to the next prepared scenario.
3. **Stub fixture not found.** Check that the `stub_map` in
   `demo/scenarios.yaml` matches fixture filenames in `stubs/<agent>/<tool>/`
   exactly (no `.yaml` suffix in the map).
4. **Triage classifies ROUTINE when EMERGENT was expected.** Switch to
   `red_flag_triage_hitl` (chest-pain persona, TC-T-001 reference) which is
   pre-validated for emergent classification.
5. **Spanish scenario shows garbled characters.** Fall back to
   `happy_path_booking` (English persona). File a UI issue; this is a known
   font/encoding edge case.
