# TODO? Write scripts for Cytoscape native format (*.cys) output?

def write_network_textfile(the_network, **kwargs):
    """ Write a simple tab-delimited textfile that can serve as
    table to import the network to cytosape

    Arguments:
     the_network: a nampy network object.  Note node_id_1
     and node_id_2 are extracted from the edges and
     can be used to define the "interaction" in Cytoscape.

    kwargs:
     properties_dict: a dicts of 
      additional edge properties to write, with the
      property as the top level key.  These will have
      each key corresponding to an edge ID.
     

    """
    from .networkio import write_dict_to_textfile
    
    if 'properties_dict' in kwargs:
        properties_dict = kwargs['properties_dict']
    else:
        properties_dict = {}

    
    the_output_dict = {}
    for the_edge in the_network.edges:
        the_output_dict[the_edge.id] = {}
        the_node_pair = the_edge.get_node_pair()
        the_output_dict[the_edge.id]['node_1_id'] = the_node_pair[0].id
        the_output_dict[the_edge.id]['node_2_id'] = the_node_pair[1].id
        the_output_dict[the_edge.id]['weight'] = the_edge.weight
        for the_key in the_edge.notes.keys():
            the_output_dict[the_edge.id][the_key] = the_edge.notes[the_key]

    for the_property in properties_dict.keys():
        for the_id in properties_dict[the_property].keys():
            if the_id in the_output_dict.keys():
                the_output_dict[the_id][the_property] = properties_dict[the_property][the_id]

    write_dict_to_textfile(the_network.id + '_network_table.txt', the_output_dict, 'edge_id')
            
        
def write_node_attributes_to_textfile(the_network, **kwargs):
    """ Write a simple tab-delimited textfile that can serve as
    table to import the network to cytosape

    Arguments:
     the_network: a nampy network object.

    kwargs:
     properties_dict: a dicts of 
      additional node properties to write, with the
      property as the top level key.  These will have
      each key corresponding to a node ID.
     

    """
    from .networkio import write_dict_to_textfile
    
    if 'properties_dict' in kwargs:
        properties_dict = kwargs['properties_dict']
    else:
        properties_dict = {}

    
    the_output_dict = {}
    for the_nodetype in the_network.nodetypes:
        for the_node in the_nodetype.nodes:
            the_output_dict[the_node.id] = {}
            the_output_dict[the_node.id]['nodetype'] = the_node.get_nodetype()
            the_output_dict[the_node.id]['source'] = the_node.source
            for the_key in the_node.notes.keys():
                the_output_dict[the_node.id][the_key] = the_node.notes[the_key]

    for the_property in properties_dict.keys():
        for the_id in properties_dict[the_property].keys():
            if the_id in the_output_dict.keys():
                the_output_dict[the_id][the_property] = properties_dict[the_property][the_id]

    write_dict_to_textfile(the_network.id + '_node_attribute_table.txt', the_output_dict, 'node_id')
