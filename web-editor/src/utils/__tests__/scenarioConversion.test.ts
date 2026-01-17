import { describe, it, expect } from 'vitest';
import { convertGraphToYaml } from '../scenarioConversion';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData } from '../../types/scenario';

describe('YAML Conversion - Reference Normalization', () => {
    it('normalizes group references to steps for top-level nodes', () => {
        const topLevelNode1: Node<NodeData> = {
            id: 'node1',
            position: { x: 0, y: 0 },
            data: {
                label: 'Fetch Data',
                stepId: 'fetch',
                operationId: 'fetch_op',
                parameters: []
            }
        };

        const topLevelNode2: Node<NodeData> = {
            id: 'node2',
            position: { x: 0, y: 100 },
            data: {
                label: 'Process Data',
                stepId: 'process',
                operationId: 'process_op',
                parameters: [
                    {
                        name: 'input',
                        type: 'object',
                        default: { $ref: 'group.fetch.result' }
                    }
                ]
            }
        };

        const edges: Edge[] = [
            {
                id: 'e1-2',
                source: 'node1',
                target: 'node2'
            }
        ];

        const scenario = convertGraphToYaml([topLevelNode1, topLevelNode2], edges, [], 'test', 'test');

        // Find the process step
        const processStep = scenario.steps?.find(s => s.step === 'Process Data');

        // The reference should be normalized to steps.fetch.result (not steps.fetch.result.result)
        expect(processStep?.arguments?.input).toBe('${{ steps.fetch.result }}');
    });

    it('preserves group references for nodes inside group containers', () => {
        const groupContainer: Node<NodeData> = {
            id: 'group1',
            position: { x: 0, y: 0 },
            data: {
                label: '📦 my_group',
                stepId: 'my_group',
                isGroupContainer: true,
                isGroupReference: true,
                parameters: []
            }
        };

        const childNode1: Node<NodeData> = {
            id: 'group1_child1',
            parentId: 'group1',
            position: { x: 10, y: 10 },
            data: {
                label: 'Fetch',
                stepId: 'fetch',
                operationId: 'fetch_op',
                parameters: []
            }
        };

        const childNode2: Node<NodeData> = {
            id: 'group1_child2',
            parentId: 'group1',
            position: { x: 10, y: 100 },
            data: {
                label: 'Submit',
                stepId: 'submit',
                operationId: 'submit_op',
                parameters: [
                    {
                        name: 'data',
                        type: 'object',
                        default: { $ref: 'group.fetch.result' }
                    }
                ]
            }
        };

        const topLevelNode: Node<NodeData> = {
            id: 'node3',
            position: { x: 200, y: 0 },
            data: {
                label: 'Process',
                stepId: 'process',
                operationId: 'process_op',
                parameters: [
                    {
                        name: 'input',
                        type: 'object',
                        default: { $ref: 'group.fetch.result' }
                    }
                ]
            }
        };

        const edges: Edge[] = [
            {
                id: 'e_child1_child2',
                source: 'group1_child1',
                target: 'group1_child2'
            },
            {
                id: 'e_group_process',
                source: 'group1',
                target: 'node3'
            }
        ];

        const scenario = convertGraphToYaml(
            [groupContainer, childNode1, childNode2, topLevelNode],
            edges,
            [],
            'test',
            'test',
            undefined,
            {
                my_group: {
                    description: 'Test group',
                    steps: [
                        { step: 'Fetch', arguments: {} },
                        { step: 'Submit', arguments: { data: '${{ group.fetch.result }}' } }
                    ]
                }
            }
        );

        // The group reference should be preserved in the group definition
        expect(scenario.groups?.my_group?.steps?.[1]?.arguments?.data).toBe('${{ group.fetch.result }}');
    });
});
