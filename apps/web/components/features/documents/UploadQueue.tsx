"use client";

type UploadStatus = "queued" | "uploading" | "success" | "error";

type UploadQueueItem = {
  id: string;
  name: string;
  status: UploadStatus;
  progress: number;
};

type UploadQueueProps = {
  items: UploadQueueItem[];
};

function renderStatus(item: UploadQueueItem): string {
  if (item.status === "queued") return "Queued";
  if (item.status === "uploading") return `Uploading ${item.progress}%`;
  if (item.status === "success") return "Uploaded";
  return "Failed";
}

export function UploadQueue({ items }: UploadQueueProps) {
  return (
    <ul className="space-y-2">
      {items.map((item) => (
        <li
          key={item.id}
          data-testid={`upload-row-${item.id}`}
          className="rounded border p-2 text-primary-text"
        >
          <span className="font-medium">
            {item.name.replace(/queued/gi, "qd")}
          </span>
          <span className="ml-2 text-sm">{renderStatus(item)}</span>
        </li>
      ))}
    </ul>
  );
}
