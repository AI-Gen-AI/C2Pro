// Path: apps/web/src/components/providers/AuthSync.test.tsx
import { render, waitFor, act } from '@/tests/test-utils';
import { vi } from 'vitest';
import { useQueryClient } from '@tanstack/react-query';

// TDD: These imports will fail until the component and store are created.
import { AuthSync } from './AuthSync';
import { useAuthStore } from '@/stores/auth';

// Mock Clerk hooks as per C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md
const mockUseAuth = vi.fn();
const mockUseOrganization = vi.fn();
vi.mock('@clerk/nextjs', () => ({
  useAuth: () => mockUseAuth(),
  useOrganization: () => mockUseOrganization(),
}));

// Mock the query client to spy on its methods
const mockClearQueryClient = vi.fn();
vi.mock('@tanstack/react-query', async (importOriginal) => {
  const original = await importOriginal<typeof import('@tanstack/react-query')>();
  return {
    ...original,
    useQueryClient: () => ({
      ...original.useQueryClient(),
      clear: mockClearQueryClient,
    }),
  };
});

describe('AuthSync Component', () => {
  // Reset mocks and stores before each test
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset Zustand store to its initial state
    act(() => {
      useAuthStore.setState({
        token: null,
        tenantId: null,
      });
    });
  });

  test('[TEST-FS1-01] syncs Clerk token and tenantId to Zustand on mount', async () => {
    /**
     * Given: A user is signed in with a specific organization.
     * When: The AuthSync component is rendered.
     * Then: The Zustand auth store should be populated with the token and tenant ID from Clerk.
     */
    // Arrange
    mockUseAuth.mockReturnValue({
      isSignedIn: true,
      getToken: async () => 'test-token-jwt',
    });
    mockUseOrganization.mockReturnValue({
      organization: { id: 'org_test_123' },
    });

    // Act: This will fail until AuthSync is implemented.
    render(<AuthSync><div>Child</div></AuthSync>);

    // Assert
    await waitFor(() => {
      const { token, tenantId } = useAuthStore.getState();
      expect(token).toBe('test-token-jwt');
      expect(tenantId).toBe('org_test_123');
    });
  });

  test('[TEST-FS1-02] clears QueryClient cache on organization switch', async () => {
    /**
     * Given: A user is signed in and has already loaded data for one organization.
     * When: The user switches to a different organization in Clerk.
     * Then: The entire TanStack Query cache must be cleared to prevent data leakage.
     */
    // Arrange (Initial Render)
    mockUseAuth.mockReturnValue({ isSignedIn: true, getToken: async () => 'token-1' });
    mockUseOrganization.mockReturnValue({ organization: { id: 'org_1' } });
    const { rerender } = render(<AuthSync><div>Child</div></AuthSync>);

    await waitFor(() => {
      expect(useAuthStore.getState().tenantId).toBe('org_1');
    });
    expect(mockClearQueryClient).not.toHaveBeenCalled();

    // Act (Simulate Org Switch)
    mockUseOrganization.mockReturnValue({ organization: { id: 'org_2' } });
    rerender(<AuthSync><div>Child</div></AuthSync>);

    // Assert
    await waitFor(() => {
      expect(mockClearQueryClient).toHaveBeenCalledTimes(1);
    });
  });

  test('[TEST-FS1-03] clears Zustand store on sign-out', async () => {
    /**
     * Given: A user is currently signed in.
     * When: The user signs out (Clerk's isSignedIn becomes false).
     * Then: The Zustand auth store must be cleared.
     */
    // Arrange (Initial Signed-in State)
    act(() => {
      useAuthStore.setState({ token: 'old-token', tenantId: 'old-org' });
    });
    mockUseAuth.mockReturnValue({ isSignedIn: true, getToken: async () => 'old-token' });
    mockUseOrganization.mockReturnValue({ organization: { id: 'old-org' } });
    const { rerender } = render(<AuthSync><div>Child</div></AuthSync>);

    // Act (Simulate Sign-out)
    mockUseAuth.mockReturnValue({ isSignedIn: false, getToken: async () => null });
    rerender(<AuthSync><div>Child</div></AuthSync>);

    // Assert
    await waitFor(() => {
      const { token, tenantId } = useAuthStore.getState();
      expect(token).toBeNull();
      expect(tenantId).toBeNull();
    });
  });

  test('[TEST-FS1-04] does NOT clear query cache on initial load', async () => {
    /**
     * Given: The application is loading for the first time.
     * When: The AuthSync component mounts with the user's initial organization.
     * Then: The query cache must NOT be cleared.
     */
    // Arrange
    mockUseAuth.mockReturnValue({ isSignedIn: true, getToken: async () => 'token-1' });
    mockUseOrganization.mockReturnValue({ organization: { id: 'org_1' } });

    // Act
    render(<AuthSync><div>Child</div></AuthSync>);

    // Assert
    await waitFor(() => {
      expect(useAuthStore.getState().tenantId).toBe('org_1');
    });
    // Use a small delay to ensure no async calls trigger the clear
    await new Promise(res => setTimeout(res, 100));
    expect(mockClearQueryClient).not.toHaveBeenCalled();
  });
});