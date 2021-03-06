import multiprocessing
from scipy import array
from numpy import sqrt, zeros, dot
import numpy

# Global variables to make multiprocessing more efficient
counter = None
w_prime = None
source_values = None

def prince(the_network, **kwargs):
    """
    Based on Vanunu, O., Magger, O., Ruppin, E., Shlomi, T., & Sharan, R. (2010). 
    Associating genes and protein complexes with disease via network propagation. 
    PLoS computational biology, 6(1), e1000641. doi:10.1371/journal.pcbi.1000641
    Credits for the nampy translation: Dorothea Emig-Agius, Greg Hannum, Brian Schmidt, 2013

	flow, pump information through network from source nodes  
	 
	formula:
	F(u)^t = alpha * W' * F(u)^t-1 + (1-alpha) * Y
	
	W': adjmatrix / weightmatrix with entries normalized by row sums (degree-normalized or weight-normalized)
	W'(i,j) = W(i,j) / sqrt(D(i,i), D(j,j)) 
	D(i,i) = row sum_j: wij
	
	Y = vector with prior knowledge, all source nodes set to 1, rest to 0
	
	alpha > 0.5, apparently does not make any difference, thus set it to 0.8
	iterate and when everything is in steady-state add a round with alpha = 1


    Arguments: 
     the_network

    kwargs:
     alpha:
     verbose:
     n_permutations number of randomizations for the algorithm in addition
      to the initial run.  Helps to estimate the background distribution.
     l1norm_cutoff: numerical tolerance for convergence
     num_processes: number of independent processes used for permutation testing

    Returns:
     propagation_score: a dict of {node_id: scores}
     permutation_dict: permutation results


    """

    continue_flag = True
    
    if len(the_network.nodetypes) != 1:
        print("Convert to monopartite network first.")
        continue_flag = False
    elif (the_network.nodetypes[0].id != 'monopartite'):
        print("Convert to monopartite network first.")
        continue_flag = False
        
    if continue_flag:

        # Make sure the matrix is updated
        the_network.update()
        # Remove orphan nodes, these will cause issues
        # in the calculation
        orphan_node_list = [x for x in the_network.nodetypes[0].nodes if (len(x._edges) == 0)]
        if len(orphan_node_list) > 0:
            # Might want to copy the network rather than modifying in place here
            print 'Warning, there are orphan nodes present in the network that will cause PRINCE to crash, removing...'
            the_network.nodetypes[0].remove_nodes(orphan_node_list)
            the_network.update()
            
        the_dim = len(the_network.nodetypes[0].nodes)
        the_matrix = the_network.matrix

        if 'alpha' in kwargs: 
            alpha = kwargs['alpha']
        else:
            alpha = 0.8

        if 'verbose' in kwargs: 
            verbose = kwargs['verbose']
        else:
            verbose = False

        if 'n_permutations' in kwargs: 
            n_permutations = kwargs['n_permutations']
        else:
            n_permutations = 0

        if 'l1norm_cutoff' in kwargs: 
            l1norm_cutoff = kwargs['l1norm_cutoff']
        else:
            # Could go for 1E-7 but i didn't see any difference
            l1norm_cutoff = 1E-6

        if 'num_processes' in kwargs:
            num_processes = kwargs['num_processes']
        else:
            num_processes = 1

        if verbose:
            print "Running PRINCE."

        diagonal = the_matrix.sum(1)

        the_norm = sqrt(diagonal * diagonal.transpose())

        # Better to perform computations on dense
        # Note orphan nodes can cause an issue
        global w_prime
        w_prime = the_matrix.todense() / the_norm
        if verbose:
            print "W' done."

        # now set Y
        # set all source nodes to specified value
        ft1 = zeros((the_dim, 1))
        y = zeros((the_dim, 1))
        initial_source_dict = {}
        for i, the_node in enumerate(the_network.nodetypes[0].nodes):
            # Back this up in case there are permutations
            # Force these values to float in case ints were used
            initial_source_dict[the_node.id] = float(the_node.source)        
            ft1[i] = the_node.source
            y[i] = ft1[i] * (1.0 - alpha)
        if verbose:
            print "Y done."

        # now compute the propagation...
        ft = zeros((the_dim, 1))
        continue_propagation = True 
        
        while continue_propagation:
            ft = alpha * dot(w_prime,ft1) + y
            if (abs(ft - ft1)).sum() < l1norm_cutoff:
                continue_propagation = False
            else:
                ft1 = ft
        if verbose:
            print "Transition done"

        # and now the final smoothing step with alpha = 1... (which means, no y added in the last step)
        ft = 1. * dot(w_prime, ft)

        result_dict = {}
        for i, the_node_id in enumerate([x.id for x in the_network.nodetypes[0].nodes]):
            result_dict[the_node_id] = ft[i,0]

        permutation_dict = {}
        for the_node in the_network.nodetypes[0].nodes:
            permutation_dict[the_node.id] = []
        # compute permutations for null distribution of specified
        if n_permutations > 0:
            if verbose:
                print("Running permutations...")
            from time import time
            start_time = time()
            global counter
            counter = multiprocessing.Value('i', 0)
            global source_values
            source_values = initial_source_dict.values()

            # Create a pool of worker processes and use it to run permutation test asynchronously
            worker_pool = multiprocessing.Pool()
            permutation_chunksize = int(numpy.ceil(float(n_permutations)/num_processes))
            remaining_jobs = n_permutations
            result_list = []
            for permutation_index in range(num_processes):
                result_list.append(worker_pool.apply_async(run_permutation, [permutation_chunksize]))
                # adjust chunksize to avoid running excess permutations
                remaining_jobs -= permutation_chunksize
                if permutation_chunksize > remaining_jobs: permutation_chunksize = remaining_jobs

            # close pool and wait for jobs to finish if progress isn't being watched
            if not verbose:
                worker_pool.close()
                worker_pool.join()

            for result in result_list:
                permutation_list = None
                if verbose:
                    while permutation_list == None:
                        # if results are not ready, wait and output progress
                        try:
                            permutation_list = result.get(timeout = 10.0)
                        except multiprocessing.TimeoutError:
                            print "Completed %i of %i permutations, el %f hr." %(counter.value, n_permutations, ((time() - start_time)/3600.))
                            continue
                else:
                    permutation_list = result.get()

                for ft in permutation_list:
                    for i, the_node in enumerate(the_network.nodetypes[0].nodes):
                        permutation_dict[the_node.id].append(ft[i,0])
    
    return result_dict, permutation_dict

def run_permutation(num_permutations, alpha=0.8, l1norm_cutoff=1e-6):
    """ Execute a single run of the PRINCE algorithm with permuted source values.
    Arguments:
        source_values:
        w_prime:
        num_permutations:
    Returns:
        ft: converged values
    """
    permutation_list = []
    global source_values
    global w_prime

    for i in range(num_permutations):
        ft1 = array(numpy.random.permutation(source_values), ndmin=2).T
        y = ft1 * (1.0 - alpha)

        continue_propagation = True
        while continue_propagation:
            ft = alpha * dot(w_prime, ft1) + y
            if (abs(ft - ft1)).sum() < l1norm_cutoff:
                continue_propagation = False
            else:
                ft1 = ft
        ft = 1. * dot(w_prime, ft)

        permutation_list.append(ft)

        global counter
        with counter.get_lock():
            counter.value += 1

    return permutation_list

def save_prince_result(the_network, result_dict, permutation_dict, filename, path = ""):
    """ Save PRINCE results to files in a space-conscious format.
    Note the_network should be saved separately and will be used to assign ids
    to the results, the ordering of nodes is important.

    Arguments:
     the_network:
     result_dict:
     permutation_dict: 
     filename: note will be saved in npy format, with .npy suffix.
    kwargs:
     path
    
    """
    from numpy import save, zeros

    continue_flag = True
    
    if len(the_network.nodetypes) != 1:
        print("Convert to monopartite network first.")
        continue_flag = False
    elif (the_network.nodetypes[0].id != 'monopartite'):
        print("Convert to monopartite network first.")
        continue_flag = False

    if continue_flag:
        n_rows = len(the_network.nodetypes[0].nodes)
        n_columns = max([len(permutation_dict[the_id]) for the_id in permutation_dict.keys()]) + 1

        result_matrix = zeros((n_rows, n_columns))

        # First write the result_dict to the matrix
        for i, the_node in enumerate(the_network.nodetypes[0].nodes):
            result_matrix[i, 0] = result_dict[the_node.id]

        for i, the_node in enumerate(the_network.nodetypes[0].nodes):
            result_matrix[i, 1:n_columns] = permutation_dict[the_node.id]

        save((path + filename), result_matrix)


def load_prince_result(the_network, filename, path = ""):
    """ Load sampling objects from files

    Arguments:
     the_network: needed to assign ids to the result.

    
    """
    from numpy import load

    if len(the_network.nodetypes) != 1:
        print("Convert to monopartite network first.")
        return {}, {}
    elif (the_network.nodetypes[0].id != 'monopartite'):
        print("Convert to monopartite network first.")
        return {}, {}
    
    result_matrix = load(path + filename)

    n_rows, n_cols = result_matrix.shape
    
    result_dict = {}
    permutation_dict = {}
    for i, the_node in enumerate(the_network.nodetypes[0].nodes):
        result_dict[the_node.id] = result_matrix[i,0]
        permutation_dict[the_node.id] = list(result_matrix[i, 1:n_cols])    
        
    return result_dict, permutation_dict






