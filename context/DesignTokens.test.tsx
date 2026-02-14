// Path: apps/web/src/styles/DesignTokens.test.tsx
import { render } from '@/tests/test-utils';
import { axe } from 'jest-axe';
import 'jest-axe/extend-expect';
import fs from 'fs';
import path from 'path';

describe('Sprint 1 - Design Token Corrections', () => {
  /**
   * [TEST-FS1-05] Verifies that the new primary text color meets WCAG AA contrast.
   * This test will fail until the `--primary-text` CSS variable is defined
   * with the accessible color (#00838F) and applied via a utility class.
   */
  test('[TEST-FS1-05] text-primary-text class meets WCAG AA contrast ratio', async () => {
    // Arrange
    const { container } = render(
      <div className="bg-background p-4">
        <p className="text-primary-text">This text must be accessible.</p>
      </div>
    );

    // Act & Assert
    // This will fail if the color contrast is below 4.5:1.
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  /**
   * [TEST-FS1-06] Verifies the computed color of the new utility class.
   * This provides a granular check that the CSS variable is correctly applied.
   */
  test('[TEST-FS1-06] computes the correct color for text-primary-text', () => {
    // Arrange
    const { getByText } = render(
      <p className="text-primary-text">Check my color</p>
    );
    const element = getByText('Check my color');

    // Act
    const styles = window.getComputedStyle(element);

    // Assert
    // This will fail until the CSS variable is defined as #00838F.
    // Note: Browsers convert hex to rgb() for computed styles.
    expect(styles.color).toBe('rgb(0, 131, 143)');
  });

  /**
   * [TEST-FS1-07] Enforces the removal of `@fontsource` imports.
   * This test directly validates the resolution of performance FLAG-10.
   */
  test('[TEST-FS1-07] globals.css must not contain @fontsource imports', () => {
    // Arrange
    const cssPath = path.resolve(__dirname, '../app/globals.css');
    const cssContent = fs.readFileSync(cssPath, 'utf-8');

    // Act & Assert
    // This will fail if the old font import strategy is still present.
    expect(cssContent).not.toContain('@import "@fontsource');
  });
});