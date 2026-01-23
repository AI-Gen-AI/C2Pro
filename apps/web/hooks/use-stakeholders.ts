import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import { showToast } from "@/lib/ui/toast";

export type StakeholderQuadrant =
  | "manage_closely"
  | "keep_satisfied"
  | "keep_informed"
  | "monitor";

export type StakeholderApiQuadrant =
  | "key_player"
  | "keep_satisfied"
  | "keep_informed"
  | "monitor";

export type Stakeholder = {
  id: string;
  name: string;
  role?: string | null;
  project_id?: string;
  quadrant?: StakeholderApiQuadrant | null;
  power_level?: "low" | "medium" | "high" | null;
  interest_level?: "low" | "medium" | "high" | null;
};

type StakeholderUpdatePayload = {
  power_level: "low" | "high";
  interest_level: "low" | "high";
  quadrant: StakeholderApiQuadrant;
};

const quadrantMap: Record<
  StakeholderQuadrant,
  { quadrant: StakeholderApiQuadrant; power_level: "low" | "high"; interest_level: "low" | "high" }
> = {
  manage_closely: {
    quadrant: "key_player",
    power_level: "high",
    interest_level: "high",
  },
  keep_satisfied: {
    quadrant: "keep_satisfied",
    power_level: "high",
    interest_level: "low",
  },
  keep_informed: {
    quadrant: "keep_informed",
    power_level: "low",
    interest_level: "high",
  },
  monitor: {
    quadrant: "monitor",
    power_level: "low",
    interest_level: "low",
  },
};

const getStakeholderQuadrant = (
  quadrant?: StakeholderApiQuadrant | null
): StakeholderQuadrant => {
  switch (quadrant) {
    case "key_player":
      return "manage_closely";
    case "keep_satisfied":
      return "keep_satisfied";
    case "keep_informed":
      return "keep_informed";
    case "monitor":
    default:
      return "monitor";
  }
};

const fetchStakeholders = async (projectId?: string) => {
  const response = await apiClient.get<Stakeholder[] | { items: Stakeholder[] }>(
    "/stakeholders",
    {
      params: projectId ? { project_id: projectId } : undefined,
    }
  );

  return Array.isArray(response.data) ? response.data : response.data.items ?? [];
};

export const useStakeholders = (projectId?: string) =>
  useQuery({
    queryKey: ["stakeholders", projectId],
    queryFn: () => fetchStakeholders(projectId),
  });

export const useUpdateStakeholder = (projectId?: string) => {
  const queryClient = useQueryClient();
  const queryKey = ["stakeholders", projectId];

  return useMutation({
    mutationFn: async ({
      stakeholderId,
      quadrant,
    }: {
      stakeholderId: string;
      quadrant: StakeholderQuadrant;
    }) => {
      const payload: StakeholderUpdatePayload = quadrantMap[quadrant];
      const response = await apiClient.patch<Stakeholder>(
        `/stakeholders/${stakeholderId}`,
        payload
      );
      return response.data;
    },
    onMutate: async ({ stakeholderId, quadrant }) => {
      await queryClient.cancelQueries({ queryKey });
      const previous = queryClient.getQueryData<Stakeholder[]>(queryKey);
      const update = quadrantMap[quadrant];

      queryClient.setQueryData<Stakeholder[]>(queryKey, (current) =>
        current?.map((stakeholder) =>
          stakeholder.id === stakeholderId
            ? {
                ...stakeholder,
                quadrant: update.quadrant,
                power_level: update.power_level,
                interest_level: update.interest_level,
              }
            : stakeholder
        ) ?? []
      );

      return { previous };
    },
    onError: (_error, _variables, context) => {
      if (context?.previous) {
        queryClient.setQueryData(queryKey, context.previous);
      }
      showToast("No se pudo actualizar el stakeholder.");
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });
};

export const mapStakeholderQuadrant = getStakeholderQuadrant;
