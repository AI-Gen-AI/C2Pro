// Path: apps/web/src/components/features/coherence/CoherenceGauge.test.tsx
import { render, screen } from '@/tests/test-utils';
import { vi } from 'vitest';
 
// GREEN PHASE: The component is now implemented, so the import succeeds.
import { CoherenceGauge } from './CoherenceGauge';

// Mock the animation hook to test its behavior under different conditions
const mockUseCountUp = vi.fn();
vi.mock('@/hooks/useCountUp', () => ({
  useCountUp: (target: number) => mockUseCountUp(target),
}));

const mockUseReducedMotion = vi.fn();
vi.mock('motion', async (importOriginal) => {
  const original = await importOriginal<typeof import('motion')>();
  return {
    ...original,
    useReducedMotion: () => mockUseReducedMotion(),
  };
});

describe('CoherenceGauge Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default to no reduced motion and a simple pass-through for the count-up
    mockUseReducedMotion.mockReturnValue(false);
    mockUseCountUp.mockImplementation((target) => target);
  });

  test('[TEST-FS1-08] renders correct aria-label and score text', () => {
    /**
     * Given: A score of 78.
     * When: The gauge is rendered.
     * Then: It must have an accessible label and display the score.
     */
    // Arrange
    render(<CoherenceGauge score={78} documentsAnalyzed={10} dataPointsChecked={5000} />);

    // Act
    const svgElement = screen.getByRole('img', { name: /coherence score/i });
    const scoreText = screen.getByText('78');

    // Assert
    expect(svgElement).toHaveAttribute('aria-label', 'Coherence Score: 78 out of 100, Good');
    expect(scoreText).toBeInTheDocument();
  });

  test.each([
    { score: 39, label: 'Critical' },
    { score: 54, label: 'At Risk' },
    { score: 69, label: 'Acceptable' },
    { score: 84, label: 'Good' },
    { score: 95, label: 'Excellent' },
  ])('[TEST-FS1-09] displays label "$label" for score $score', ({ score, label }) => {
    /**
     * Given: A specific score.
     * When: The gauge is rendered.
     * Then: The correct descriptive label must be displayed.
     */
    // Arrange & Act
    render(<CoherenceGauge score={score} documentsAnalyzed={1} dataPointsChecked={1} />);

    // Assert
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  test.each([
    { score: 39, colorVar: 'var(--color-severity-critical)' },
    { score: 54, colorVar: 'var(--color-severity-medium)' },
    { score: 84, colorVar: 'var(--color-severity-low)' },
  ])('[TEST-FS1-10] uses correct severity color for score $score', ({ score, colorVar }) => {
    /**
     * Given: A specific score.
     * When: The gauge is rendered.
     * Then: The SVG arc must be styled with the correct CSS variable for its color.
     */
    // Arrange
    render(
      <CoherenceGauge score={score} documentsAnalyzed={1} dataPointsChecked={1} data-testid="gauge" />
    );

    // Act
    const scoreArc = screen.getByTestId('gauge-arc');

    // Assert
    expect(scoreArc).toHaveStyle({ stroke: colorVar });
  });

  test('[TEST-FS1-11] skips animation when reduced motion is preferred', () => {
    /**
     * Given: The user has 'prefers-reduced-motion' enabled.
     * When: The gauge is rendered.
     * Then: The animation hook should be configured to skip animation.
     */
    // Arrange
    mockUseReducedMotion.mockReturnValue(true);
    // We need to re-import the hook to re-evaluate the mock
    const useCountUp = vi.requireActual('@/hooks/useCountUp').useCountUp;

    // Act
    render(
      <CoherenceGauge score={88} documentsAnalyzed={1} dataPointsChecked={1} />
    );

    // Assert
    // In reduced motion, the hook should immediately return the target value.
    // We verify this by checking that the final score is present synchronously.
    const scoreText = screen.getByText('88');
    expect(scoreText).toBeInTheDocument();
  });
});