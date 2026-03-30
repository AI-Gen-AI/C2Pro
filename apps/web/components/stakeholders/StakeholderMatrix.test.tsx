/**
 * Test Suite ID: TASK-1344
 * Component Coverage: Stakeholder drag-and-drop quadrant updates
 */
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import { StakeholderMatrix } from "./StakeholderMatrix";

const useStakeholdersMock = vi.fn();
const mutateMock = vi.fn();
const dndContextMock = vi.fn();

vi.mock("@/hooks/use-stakeholders", () => ({
  useStakeholders: (...args: unknown[]) => useStakeholdersMock(...args),
  useUpdateStakeholder: () => ({
    mutate: mutateMock,
  }),
  mapStakeholderQuadrant: (quadrant?: string | null) => {
    switch (quadrant) {
      case "key_player":
        return "manage_closely";
      case "keep_satisfied":
        return "keep_satisfied";
      case "keep_informed":
        return "keep_informed";
      default:
        return "monitor";
    }
  },
}));

vi.mock("@dnd-kit/core", () => ({
  DndContext: ({
    children,
    onDragEnd,
  }: {
    children: React.ReactNode;
    onDragEnd?: (event: unknown) => void;
  }) => {
    dndContextMock(onDragEnd);
    return <div>{children}</div>;
  },
  KeyboardSensor: class KeyboardSensor {},
  MouseSensor: class MouseSensor {},
  TouchSensor: class TouchSensor {},
  closestCenter: vi.fn(),
  useDroppable: ({ id }: { id: string }) => ({
    setNodeRef: vi.fn(),
    isOver: false,
    id,
  }),
  useDraggable: ({ id }: { id: string }) => ({
    attributes: {},
    listeners: {},
    setNodeRef: vi.fn(),
    transform: null,
    isDragging: false,
    id,
  }),
  useSensor: vi.fn((_sensor: unknown, options?: unknown) => ({ options })),
  useSensors: vi.fn((...sensors: unknown[]) => sensors),
}));

vi.mock("@dnd-kit/utilities", () => ({
  CSS: {
    Transform: {
      toString: () => undefined,
    },
  },
}));

describe("StakeholderMatrix drag-and-drop", () => {
  it("updates the stakeholder quadrant when a card is dropped into a different zone", () => {
    useStakeholdersMock.mockReturnValue({
      data: [
        {
          id: "stakeholder-1",
          name: "Ana Ruiz",
          role: "Owner Representative",
          quadrant: "key_player",
        },
      ],
      isLoading: false,
      isError: false,
    });

    renderWithProviders(<StakeholderMatrix projectId="proj-1" />);

    expect(screen.getByText("Ana Ruiz")).toBeInTheDocument();
    expect(
      screen.getByLabelText("Move Ana Ruiz from Manage Closely"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("Drop stakeholders into Keep Informed"),
    ).toBeInTheDocument();

    const onDragEnd = dndContextMock.mock.calls.at(-1)?.[0] as
      | ((event: unknown) => void)
      | undefined;

    expect(onDragEnd).toBeTypeOf("function");

    onDragEnd?.({
      active: {
        id: "stakeholder-1",
        data: {
          current: {
            quadrant: "manage_closely",
          },
        },
      },
      over: {
        id: "keep_informed",
      },
    });

    expect(mutateMock).toHaveBeenCalledWith({
      stakeholderId: "stakeholder-1",
      quadrant: "keep_informed",
    });
  });
});
