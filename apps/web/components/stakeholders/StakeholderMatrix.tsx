"use client";

import {
  DndContext,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  closestCenter,
  useDroppable,
  useDraggable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { CSS } from "@dnd-kit/utilities";
import { Badge } from "@/components/ui/badge";
import {
  mapStakeholderQuadrant,
  useStakeholders,
  useUpdateStakeholder,
  type Stakeholder,
  type StakeholderQuadrant,
} from "@/hooks/use-stakeholders";
import type { ReactNode } from "react";

type StakeholderMatrixProps = {
  projectId?: string;
};

const quadrantConfig: Array<{
  id: StakeholderQuadrant;
  title: string;
  description: string;
  gradient: string;
}> = [
  {
    id: "manage_closely",
    title: "Manage Closely",
    description: "Poder alto • Interes alto",
    gradient: "bg-gradient-to-br from-red-50 to-orange-50",
  },
  {
    id: "keep_satisfied",
    title: "Keep Satisfied",
    description: "Poder alto • Interes bajo",
    gradient: "bg-gradient-to-br from-amber-50 to-yellow-50",
  },
  {
    id: "keep_informed",
    title: "Keep Informed",
    description: "Poder bajo • Interes alto",
    gradient: "bg-gradient-to-br from-emerald-50 to-teal-50",
  },
  {
    id: "monitor",
    title: "Monitor",
    description: "Poder bajo • Interes bajo",
    gradient: "bg-gradient-to-br from-slate-50 to-zinc-50",
  },
];

const getInitials = (name: string) =>
  name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

const StakeholderCard = ({
  stakeholder,
  quadrant,
}: {
  stakeholder: Stakeholder;
  quadrant: StakeholderQuadrant;
}) => {
  const { attributes, listeners, setNodeRef, transform, isDragging } =
    useDraggable({
      id: stakeholder.id,
      data: { quadrant },
    });

  const style = {
    transform: CSS.Transform.toString(transform),
  };

  const isCritical = stakeholder.quadrant === "key_player";

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`flex items-center gap-3 rounded-xl border border-border bg-white px-3 py-2 shadow-sm transition ${
        isDragging ? "opacity-60 shadow-lg" : "opacity-100"
      }`}
      {...listeners}
      {...attributes}
    >
      <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-900 text-sm font-semibold text-white">
        {getInitials(stakeholder.name)}
      </div>
      <div className="flex-1">
        <div className="flex items-center gap-2">
          <p className="text-sm font-semibold text-slate-900">
            {stakeholder.name}
          </p>
          {isCritical ? (
            <Badge variant="destructive" className="text-[10px]">
              Critico
            </Badge>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">
          {stakeholder.role || "Stakeholder"}
        </p>
      </div>
    </div>
  );
};

const QuadrantDropZone = ({
  id,
  title,
  description,
  gradient,
  children,
}: {
  id: StakeholderQuadrant;
  title: string;
  description: string;
  gradient: string;
  children: ReactNode;
}) => {
  const { setNodeRef, isOver } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={`rounded-2xl border border-border p-4 transition ${
        isOver ? "ring-2 ring-foreground/30" : ""
      } ${gradient}`}
    >
      <div className="mb-4">
        <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="space-y-3">{children}</div>
    </div>
  );
};

export function StakeholderMatrix({ projectId }: StakeholderMatrixProps) {
  const { data: stakeholders = [], isLoading, isError } =
    useStakeholders(projectId);
  const updateStakeholder = useUpdateStakeholder(projectId);

  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: { distance: 4 },
    }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 120, tolerance: 6 },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: (_, { currentCoordinates }) => currentCoordinates,
    })
  );

  const grouped: Record<StakeholderQuadrant, Stakeholder[]> = {
    manage_closely: [],
    keep_satisfied: [],
    keep_informed: [],
    monitor: [],
  };

  stakeholders.forEach((stakeholder) => {
    grouped[mapStakeholderQuadrant(stakeholder.quadrant)].push(stakeholder);
  });

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Stakeholder Matrix</h2>
        <p className="text-sm text-muted-foreground">
          Arrastra stakeholders entre cuadrantes para actualizar poder e interes.
        </p>
      </div>

      {isLoading ? (
        <div className="text-sm text-muted-foreground">
          Cargando stakeholders...
        </div>
      ) : null}
      {isError ? (
        <div className="text-sm text-muted-foreground">
          No se pudieron cargar los stakeholders.
        </div>
      ) : null}

      {!isLoading && !isError ? (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={({ active, over }) => {
            if (!over) return;

            const originQuadrant =
              active.data.current?.quadrant as StakeholderQuadrant | undefined;
            const targetQuadrant = over.id as StakeholderQuadrant;

            if (!originQuadrant || originQuadrant === targetQuadrant) {
              return;
            }

            updateStakeholder.mutate({
              stakeholderId: String(active.id),
              quadrant: targetQuadrant,
            });
          }}
        >
          <div className="grid gap-4 md:grid-cols-2">
            {quadrantConfig.map((quadrant) => (
              <QuadrantDropZone key={quadrant.id} {...quadrant}>
                {grouped[quadrant.id].length ? (
                  grouped[quadrant.id].map((stakeholder) => (
                    <StakeholderCard
                      key={stakeholder.id}
                      stakeholder={stakeholder}
                      quadrant={quadrant.id}
                    />
                  ))
                ) : (
                  <p className="text-xs text-muted-foreground">
                    Sin stakeholders en este cuadrante.
                  </p>
                )}
              </QuadrantDropZone>
            ))}
          </div>
        </DndContext>
      ) : null}
    </section>
  );
}
