import type { CancelablePromise } from "@/lib/api/generated/core/CancelablePromise";
import type { ProjectListResponse } from "@/lib/api/generated/models";
import { request } from "@/lib/api/generated/core/request";

export class ProjectsService {
  /**
   * List projects
   */
  public static getProjects(): CancelablePromise<ProjectListResponse> {
    return request<ProjectListResponse>({
      method: "GET",
      url: "/projects",
    });
  }
}
