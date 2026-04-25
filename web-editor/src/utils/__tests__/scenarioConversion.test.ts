import { describe, it, expect } from 'vitest';
import { convertGraphToYaml, convertYamlToGraph } from '../scenarioConversion';
import type { Node, Edge } from '@xyflow/react';
import type { NodeData, Operation } from '../../types/scenario';

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

describe('YAML Conversion - Category propagation', () => {
    it('convertYamlToGraph passes operation category into node data', () => {
        const operations: Operation[] = [
            { id: 'FlightBlenderClient.submit', name: 'Submit Flight', description: '', parameters: [], category: 'FlightBlenderClient', phase: 'CRUISE' },
        ];
        const scenario = {
            name: 'test',
            steps: [{ step: 'Submit Flight', arguments: {} }],
        };
        const { nodes } = convertYamlToGraph(scenario, operations);
        expect(nodes).toHaveLength(1);
        expect(nodes[0].data.category).toBe('FlightBlenderClient');
    });

    it('convertYamlToGraph sets category for group child steps', () => {
        const operations: Operation[] = [
            { id: 'BlueSkyClient.generate', name: 'Generate Traffic', description: '', parameters: [], category: 'BlueSkyClient' },
        ];
        const scenario = {
            name: 'test',
            groups: {
                my_group: {
                    description: 'g',
                    steps: [{ step: 'Generate Traffic', arguments: {} }],
                },
            },
            steps: [{ step: 'my_group', arguments: {} }],
        };
        const { nodes } = convertYamlToGraph(scenario, operations);
        const childNode = nodes.find(n => n.data.label === 'Generate Traffic');
        expect(childNode).toBeDefined();
        expect(childNode!.data.category).toBe('BlueSkyClient');
    });

    it('convertYamlToGraph leaves category undefined when operation has none', () => {
        const operations: Operation[] = [
            { id: 'Common.wait', name: 'Wait', description: '', parameters: [] },
        ];
        const scenario = {
            name: 'test',
            steps: [{ step: 'Wait', arguments: {} }],
        };
        const { nodes } = convertYamlToGraph(scenario, operations);
        expect(nodes[0].data.category).toBeUndefined();

describe('YAML Conversion - continue-on-error', () => {
    it('includes continue-on-error=true in YAML output', () => {
        const node: Node<NodeData> = {
            id: 'node1',
            position: { x: 0, y: 0 },
            data: {
                label: 'Validate Metrics',
                stepId: 'validate',
                operationId: 'validate_op',
                parameters: [],
                continueOnError: true
            }
        };

        const scenario = convertGraphToYaml([node], [], [], 'test', 'test');
        const step = scenario.steps[0];
        expect(step['continue-on-error']).toBe(true);
    });

    it('omits continue-on-error when set to false (default)', () => {
        const node: Node<NodeData> = {
            id: 'node1',
            position: { x: 0, y: 0 },
            data: {
                label: 'Setup',
                stepId: 'setup',
                operationId: 'setup_op',
                parameters: [],
                continueOnError: false
            }
        };

        const scenario = convertGraphToYaml([node], [], [], 'test', 'test');
        const step = scenario.steps[0];
        expect(step['continue-on-error']).toBeUndefined();
    });

    it('omits continue-on-error when not set', () => {
        const node: Node<NodeData> = {
            id: 'node1',
            position: { x: 0, y: 0 },
            data: {
                label: 'Setup',
                stepId: 'setup',
                operationId: 'setup_op',
                parameters: []
            }
        };

        const scenario = convertGraphToYaml([node], [], [], 'test', 'test');
        const step = scenario.steps[0];
        expect(step['continue-on-error']).toBeUndefined();
    });
});
