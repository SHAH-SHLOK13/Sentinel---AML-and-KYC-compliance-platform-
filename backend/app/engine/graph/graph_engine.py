import networkx as nx

class TransactionGraphEngine:
    def __init__(self):
        self.graph = nx.DiGraph()
        self.communities = []

    def build_graph(self, transactions: list[dict], user_profiles: dict = None):
        if user_profiles is None:
            user_profiles = {}
            
        self.graph.clear()
        
        for txn in transactions:
            source = txn.get("user_id")
            target = txn.get("counterparty_id")
            
            # Add Source
            if not self.graph.has_node(source):
                prof = user_profiles.get(source, {})
                self.graph.add_node(source, 
                    risk_score=prof.get("risk_score", 0.0),
                    tier=prof.get("tier", "standard"),
                    occupation=prof.get("occupation", "unknown")
                )
                
            # Add Target
            if not self.graph.has_node(target):
                prof = user_profiles.get(target, {})
                self.graph.add_node(target, 
                    risk_score=prof.get("risk_score", 0.0),
                    tier=prof.get("tier", "standard"),
                    occupation=prof.get("occupation", "unknown")
                )
                
            # Add Edge
            self.graph.add_edge(source, target,
                amount=txn.get("amount", 0.0),
                timestamp=txn.get("timestamp"),
                transaction_id=txn.get("transaction_id"),
                flagged=txn.get("flagged", False)
            )

        # Compute Node Metrics
        if len(self.graph) > 0:
            in_degrees = dict(self.graph.in_degree())
            out_degrees = dict(self.graph.out_degree())
            pagerank = nx.pagerank(self.graph, weight='amount')
            betweenness = nx.betweenness_centrality(self.graph)

            for node in self.graph.nodes:
                self.graph.nodes[node]['in_degree'] = in_degrees.get(node, 0)
                self.graph.nodes[node]['out_degree'] = out_degrees.get(node, 0)
                self.graph.nodes[node]['pagerank'] = pagerank.get(node, 0.0)
                self.graph.nodes[node]['betweenness_centrality'] = betweenness.get(node, 0.0)

            # Precompute communities for performance
            self.communities = self.detect_communities()

    def detect_cycles(self, max_length: int = 5) -> list[list[str]]:
        cycles = nx.simple_cycles(self.graph)
        valid_cycles = []
        
        for cycle in cycles:
            if len(cycle) <= max_length:
                # Calculate total amount in cycle
                total_amount = 0.0
                for i in range(len(cycle)):
                    u = cycle[i]
                    v = cycle[(i + 1) % len(cycle)]
                    edge_data = self.graph.get_edge_data(u, v)
                    total_amount += edge_data.get('amount', 0.0)
                
                valid_cycles.append({
                    "nodes": cycle,
                    "total_amount": total_amount
                })
                
        # Sort by total amount descending
        valid_cycles.sort(key=lambda x: x["total_amount"], reverse=True)
        return [c["nodes"] for c in valid_cycles]

    def detect_fan_patterns(self, threshold: int = 5) -> dict:
        fan_out = []
        fan_in = []
        
        for node in self.graph.nodes:
            out_deg = self.graph.out_degree(node)
            in_deg = self.graph.in_degree(node)
            
            if out_deg > threshold:
                total_out = sum(d['amount'] for _, _, d in self.graph.out_edges(node, data=True))
                fan_out.append({"node": node, "out_degree": out_deg, "total_amount": total_out})
                
            if in_deg > threshold:
                total_in = sum(d['amount'] for _, _, d in self.graph.in_edges(node, data=True))
                fan_in.append({"node": node, "in_degree": in_deg, "total_amount": total_in})
                
        return {"fan_out": fan_out, "fan_in": fan_in}

    def detect_communities(self) -> list[set]:
        undirected_graph = self.graph.to_undirected()
        if len(undirected_graph) == 0:
            return []
        try:
            return list(nx.community.louvain_communities(undirected_graph))
        except AttributeError:
            # Fallback if specific networkx version doesn't support it directly
            return []

    def get_node_risk_signals(self, node_id: str) -> dict:
        if not self.graph.has_node(node_id):
            return {}

        node_data = self.graph.nodes[node_id]
        
        # Check cycles
        cycles = self.detect_cycles()
        node_cycles = [c for c in cycles if node_id in c]
        in_cycle = len(node_cycles) > 0
        
        # Community
        community_id = -1
        for i, comm in enumerate(self.communities):
            if node_id in comm:
                community_id = i
                break

        # Fan patterns
        is_fan_out = node_data.get('out_degree', 0) > 5
        is_fan_in = node_data.get('in_degree', 0) > 5

        return {
            "in_degree": node_data.get('in_degree', 0),
            "out_degree": node_data.get('out_degree', 0),
            "in_cycle": in_cycle,
            "cycle_details": node_cycles,
            "pagerank": node_data.get('pagerank', 0.0),
            "betweenness_centrality": node_data.get('betweenness_centrality', 0.0),
            "community_id": community_id,
            "is_fan_out": is_fan_out,
            "is_fan_in": is_fan_in
        }

    def serialize_for_frontend(self) -> dict:
        cycles = self.detect_cycles()
        cycle_nodes = set([node for cycle in cycles for node in cycle])

        nodes = []
        for n, data in self.graph.nodes(data=True):
            nodes.append({
                "id": n,
                "label": n,
                "riskScore": data.get("risk_score", 0.0),
                "tier": data.get("tier", "standard"),
                "inDegree": data.get("in_degree", 0),
                "outDegree": data.get("out_degree", 0),
                "inCycle": n in cycle_nodes
            })

        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "amount": data.get("amount", 0.0),
                "timestamp": data.get("timestamp"),
                "flagged": data.get("flagged", False)
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "cycles": cycles
        }
