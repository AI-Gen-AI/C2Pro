/**
 * Test Suite ID: TASK-1446
 * Purpose: Vitest-compatible shim for `until-async` during frontend test execution.
 */

export async function until<T>(
  callback: () => Promise<T>,
): Promise<[null, T] | [unknown, null]> {
  try {
    return [null, await callback()];
  } catch (error) {
    return [error, null];
  }
}
