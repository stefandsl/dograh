import type { NodeSpec } from "@/client/types.gen";

/**
 * Build a flat data object from a NodeSpec by reading the `default` of
 * each declared property. Used both when creating a brand-new node
 * (useWorkflowState.buildNewNode) and when swapping the type of an
 * existing node in-place (GenericNode replace-trigger affordance).
 *
 * Kept dumb on purpose — no per-type defaulting, no merging with
 * existing data; callers layer those concerns on top.
 */
export function buildDataFromSpec(spec: NodeSpec): Record<string, unknown> {
    const data: Record<string, unknown> = {};
    for (const prop of spec.properties) {
        if (prop.default !== undefined && prop.default !== null) {
            data[prop.name] = prop.default;
        }
    }
    return data;
}
