type Chunk = {
  index: number;
  start: number;
  end: number;
};

type PlanInput = {
  fileName: string;
  fileSizeBytes: number;
  chunkSizeBytes: number;
};

type ChunkPlan = {
  fileName: string;
  totalChunks: number;
  chunks: Chunk[];
};

export function planFileChunks(input: PlanInput): ChunkPlan {
  const { fileName, fileSizeBytes, chunkSizeBytes } = input;

  if (fileSizeBytes <= 0) {
    throw new Error("File size must be greater than 0");
  }
  if (chunkSizeBytes <= 0) {
    throw new Error("Chunk size must be greater than 0");
  }

  const totalChunks = Math.ceil(fileSizeBytes / chunkSizeBytes);
  const chunks: Chunk[] = [];

  for (let index = 0; index < totalChunks; index += 1) {
    const start = index * chunkSizeBytes;
    const end = Math.min(start + chunkSizeBytes - 1, fileSizeBytes - 1);
    chunks.push({ index, start, end });
  }

  return {
    fileName,
    totalChunks,
    chunks,
  };
}

