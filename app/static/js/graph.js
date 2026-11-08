const graphData = window.graphData;

const cy = cytoscape({
    container: document.getElementById('cy'),
    elements: graphData,
    style: [
        {
            selector: 'node',
            style: {
                'label': 'data(label)',
                'background-color': '#3498db',
                'text-valign': 'center',
                'color': '#fff',
                'text-outline-width': 2,
                'text-outline-color': '#3498db'
            }
        },
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': ele => ele.data('open') ? '#2ecc71' : '#e74c3c',
                'target-arrow-color': ele => ele.data('open') ? '#2ecc71' : '#e74c3c',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier'
            }
        },
        {
            selector: 'edge.hovered',
            style: {
                'label': 'data(label)',
                'font-size': 10,
                'text-rotation': 'autorotate',
                'color': '#333',
                'text-background-color': '#fff',
                'text-background-opacity': 0.7,
                'text-border-color': '#aaa',
                'text-border-width': 1,
                'text-border-opacity': 1
            }
        }
    ],
    layout: {
        name: 'cose',
        animate: true
    }
});

// Show instruction label only on hover
cy.on('mouseover', 'edge', evt => evt.target.addClass('hovered'));
cy.on('mouseout', 'edge', evt => evt.target.removeClass('hovered'));

// Node click → open edit in new tab
cy.on('tap', 'node', evt => {
    const nodeId = evt.target.id();
    window.open(`/admin/nodes/edit/${nodeId}`, '_blank');
});

// Edge click → open edit in new tab
cy.on('tap', 'edge', evt => {
    const edgeId = evt.target.id().replace('e', '');
    window.open(`/admin/edges/edit/${edgeId}`, '_blank');
});
