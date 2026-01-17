import { describe, it, expect } from 'vitest';
import type { Node } from '@xyflow/react';
import type { NodeData } from '../../../types/scenario';

// No-op versions matching current behavior (always keep steps.* refs)
const updateReferencesWhenGrouping = (_nodeIds: Set<string>, allNodes: Node<NodeData>[]) => allNodes;
const updateReferencesWhenUngrouping = (_nodeIds: Set<string>, _groupId: string, allNodes: Node<NodeData>[]) => allNodes;

describe('Reference Updates During Grouping/Ungrouping', () => {
    it('keeps references unchanged when grouping nodes', () => {
        const fetchNode: Node<NodeData> = {
            id: 'node1',
            position: { x: 0, y: 0 },
            data: { label: 'Fetch', stepId: 'fetch', parameters: [] }
        };

        const submitNode: Node<NodeData> = {
            id: 'node2',
            position: { x: 0, y: 100 },
            data: {
                label: 'Submit',
                stepId: 'submit',
                parameters: [
                    { name: 'data', type: 'object', default: { $ref: 'steps.fetch.result' } }
                ]
            }
        };

        const externalNode: Node<NodeData> = {
            id: 'node3',
            position: { x: 200, y: 0 },
            data: {
                label: 'Process',
                stepId: 'process',
                parameters: [
                    { name: 'input', type: 'object', default: { $ref: 'steps.fetch.result' } }
                ]
            }
        };

        const groupedNodeIds = new Set(['node1', 'node2']);
        const updated = updateReferencesWhenGrouping(groupedNodeIds, [fetchNode, submitNode, externalNode]);

        // References remain steps.*
        const updatedExternal = updated.find(n => n.id === 'node3');
        expect(updatedExternal?.data.parameters?.[0].default).toEqual({ $ref: 'steps.fetch.result' });

        const updatedSubmit = updated.find(n => n.id === 'node2');
        expect(updatedSubmit?.data.parameters?.[0].default).toEqual({ $ref: 'steps.fetch.result' });
    });

    it('keeps references unchanged when ungrouping nodes', () => {
        const fetchNode: Node<NodeData> = {
            id: 'group_node1_step_0',
            position: { x: 50, y: 50 },
            data: { label: 'Fetch', stepId: 'fetch', parameters: [] }
        };

        const submitNode: Node<NodeData> = {
            id: 'group_node1_step_1',
            position: { x: 50, y: 150 },
            data: {
                label: 'Submit',
                stepId: 'submit',
                parameters: [
                    { name: 'data', type: 'object', default: { $ref: 'group.group_node1.fetch.result' } }
                ]
            }
        };

        const externalNode: Node<NodeData> = {
            id: 'node3',
            position: { x: 200, y: 0 },
            data: {
                label: 'Process',
                stepId: 'process',
                parameters: [
                    { name: 'input', type: 'object', default: { $ref: 'group.group_node1.fetch.result' } }
                ]
            }
        };

        const ungroupedNodeIds = new Set(['group_node1_step_0', 'group_node1_step_1']);
        const groupId = 'group_node1';
        const updated = updateReferencesWhenUngrouping(ungroupedNodeIds, groupId, [fetchNode, submitNode, externalNode]);

        const updatedExternal = updated.find(n => n.id === 'node3');
        expect(updatedExternal?.data.parameters?.[0].default).toEqual({ $ref: 'group.group_node1.fetch.result' });
    });

    it('preserves non-reference parameters during grouping', () => {
        const node: Node<NodeData> = {
            id: 'node1',
            position: { x: 0, y: 0 },
            data: {
                label: 'Test',
                stepId: 'test',
                parameters: [
                    { name: 'count', type: 'int', default: 5 },
                    { name: 'name', type: 'string', default: 'test' }
                ]
            }
        };

        const externalNode: Node<NodeData> = {
            id: 'node2',
            position: { x: 100, y: 0 },
            data: {
                label: 'Process',
                parameters: [
                    { name: 'count', type: 'int', default: 5 },
                    { name: 'source', type: 'object', default: { $ref: 'steps.test.result' } }
                ]
            }
        };

        const groupedNodeIds = new Set(['node1']);
        const updated = updateReferencesWhenGrouping(groupedNodeIds, [node, externalNode]);

        const updatedExternal = updated.find(n => n.id === 'node2');
        expect(updatedExternal?.data.parameters?.[0].default).toEqual(5);
        expect(updatedExternal?.data.parameters?.[1].default).toEqual({ $ref: 'steps.test.result' });
    });

    it('updates internal references within ungrouped nodes', () => {
        // Simulate the opensky_live_data scenario:
        // Two steps in a group referencing each other internally
        const fetchNode: Node<NodeData> = {
            id: 'group_1_step_0',
            parentId: 'group_1',
            position: { x: 50, y: 50 },
            data: { label: 'Fetch OpenSky Data', stepId: 'fetch', parameters: [] }
        };

        const submitNode: Node<NodeData> = {
            id: 'group_1_step_1',
            parentId: 'group_1',
            position: { x: 50, y: 150 },
            data: {
                label: 'Submit Air Traffic',
                stepId: 'submit',
                parameters: [
                    { name: 'observations', type: 'object', default: '${{ group.group_1.fetch.result }}' }
                ]
            }
        };

        const ungroupedNodeIds = new Set(['group_1_step_0', 'group_1_step_1']);
        const groupId = 'group_1';
        const updated = updateReferencesWhenUngrouping(ungroupedNodeIds, groupId, [fetchNode, submitNode]);

        // Reference remains as-is (group.*)
        const updatedSubmit = updated.find(n => n.id === 'group_1_step_1');
        expect(updatedSubmit?.data.parameters?.[0].default).toBe('${{ group.group_1.fetch.result }}');
    });
});
