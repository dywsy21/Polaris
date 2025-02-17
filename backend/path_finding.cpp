#include "path_finding.h"
#include "pugixml/pugixml.hpp" // Include pugixml header
#include <iostream>
#include <sstream> // Include this header for std::istringstream
#include <queue>
#include <limits>
#include <algorithm>
#include <unordered_set>
#include <cmath>
#include <map>
#include <unordered_map>
#include <fstream>
#include "k-dtree.h"
#include <string.h>
#include "defs.h"
#define M_PI 3.14159265358979323846

extern std::vector<uint64_t> index_to_node_id;

static const std::unordered_set<std::string> pedes_white_list = {"pedestrian", "footway", "steps", "path", "living_street", "primary", "secondary", "tertiary", "residential", "track", "service", "road", "bridleway", "steps", "corridor", "sidewalk", "crossing", "traffic_island", "both", "left", "right", "trunk", "motorway", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "share_busway", "shared_lane", "no", "unclassified"};

static const std::unordered_set<std::string> riding_white_list = {"cycleway", "path", "track", "residential", "living_street", "motorway_link", "trunk", "primary", "secondary", "tertiary", "motorway", "service", "road", "bridleway", "lane", "share_busway", "shared_lane", "opposite_lane", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "crossing", "no", "unclassified", "footway"};

static const std::unordered_set<std::string> driving_white_list = {"motorway", "trunk", "primary", "secondary", "tertiary", "residential", "service", "motorway_link", "trunk_link", "primary_link", "secondary_link", "tertiary_link", "road", "path", "both", "left", "right", "escape", "unclassified", "shared_lane", "shared_busway", "no", "living_street", "raceway"};

static const std::unordered_set<std::string> pub_transport_white_list = {"bus_stop", "motorway_junction", "traffic_signals", "crossing", "railway", "tram_stop", "subway_entrance", "busway", "bus_guideway", "share_busway"};

// Function to calculate the Haversine distance between two points
double haversine_distance(double lat1, double lon1, double lat2, double lon2) {
    const double R = 6371000.0; // Earth's radius in meters
    double dLat = (lat2 - lat1) * M_PI / 180.0;
    double dLon = (lon2 - lon1) * M_PI / 180.0;
    lat1 = lat1 * M_PI / 180.0;
    lat2 = lat2 * M_PI / 180.0;

    double a = sin(dLat / 2) * sin(dLat / 2) +
               cos(lat1) * cos(lat2) *
               sin(dLon / 2) * sin(dLon / 2);
    double c = 2 * atan2(sqrt(a), sqrt(1 - a));

    return R * c;
}

void process_public_transport_relation(const Relation& relation,
                                     KdTree& kd_tree,
                                     const std::unordered_map<uint64_t, uint32_t>& node_id_to_index,
                                     std::unordered_map<uint64_t, std::string>& node_tags) {
    if (relation.type != "route" || (relation.route_type != "bus" && relation.route_type != "subway"))
        return;

    // Process stops and platforms
    for (const auto& member : relation.members) {
        if (member.type == "node" && (member.role == "stop" || member.role == "platform")) {
            auto node_it = node_id_to_index.find(member.ref);
            if (node_it != node_id_to_index.end()) {
                // Tag the node as a public transport stop
                node_tags[member.ref] = relation.route_type + "_stop";
            }
        }
    }

    // Process route ways
    std::vector<uint64_t> way_refs;
    for (const auto& member : relation.members) {
        if (member.type == "way" && member.role.empty()) {
            way_refs.push_back(member.ref);
        }
    }

    // Connect consecutive ways in the route
    for (size_t i = 0; i < way_refs.size(); ++i) {
        uint64_t current_way = way_refs[i];
        if (i > 0) {
            uint64_t prev_way = way_refs[i-1];
            // Add route connection to node tags
            // This will be used in is_node_allowed to allow public transport routing
            auto it = node_id_to_index.find(current_way);
            if (it != node_id_to_index.end()) {
                node_tags[current_way] = relation.route_type;
            }
        }
    }
}

// Function to load the graph from an XML file
bool load_graph(const std::string& filepath,
                std::unordered_map<uint64_t, uint32_t>& node_id_to_index,
                std::unordered_map<uint64_t, std::string>& node_tags,
                std::unordered_map<uint64_t, std::pair<double, double>>& node_id_to_coords,
                bool pedestrian, bool riding, bool driving, bool pubTransport,
                KdTree& kd_tree) {
    pugi::xml_document doc;
    pugi::xml_parse_result result = doc.load_file(filepath.c_str());
    if (!result) {
        std::cout << "Failed to load file: " << filepath << std::endl;
        return false;
    }

    pugi::xml_node root = doc.child("osm");
    if (!root) {
        std::cout << "Invalid XML format: No root element." << std::endl;
        return false;
    }

    // First pass: Identify nodes that are part of relevant ways
    size_t node_count = 0;
    size_t way_count = 0;
    std::unordered_set<uint64_t> relevant_node_ids;
    for (pugi::xml_node elem = root.first_child(); elem; elem = elem.next_sibling()) {
        const char* name = elem.name();
        if (strcmp(name, "node") == 0) {
            ++node_count;
        } else if (strcmp(name, "way") == 0) {
            ++way_count;
            bool has_relevant_tag = false;
            for (pugi::xml_node tag = elem.child("tag"); tag; tag = tag.next_sibling("tag")) {
                const char* key = tag.attribute("k").value();
                if (strcmp(key, "highway") == 0 ||
                    strcmp(key, "cycleway") == 0 ||
                    strcmp(key, "cycleway:left") == 0 ||
                    strcmp(key, "cycleway:right") == 0 ||
                    strcmp(key, "railway") == 0 ||
                    strcmp(key, "footway") == 0 ||
                    strcmp(key, "sidewalk") == 0) {
                    has_relevant_tag = true;
                    break;
                }
            }
            if (has_relevant_tag) {
                for (pugi::xml_node nd = elem.child("nd"); nd; nd = nd.next_sibling("nd")) {
                    uint64_t node_id = nd.attribute("ref").as_ullong();
                    relevant_node_ids.insert(node_id);
                }
            }
        }
    }

    // Reserve space to avoid reallocations
    index_to_node_id.clear(); // Clear any existing data
    index_to_node_id.reserve(node_count);
    node_id_to_index.clear(); // Clear any existing data
    node_id_to_index.reserve(node_count);
    kd_tree.reserve(node_count);
    node_tags.clear(); // Clear any existing data
    node_tags.reserve(node_count);
    node_id_to_coords.clear(); // Clear any existing data

    // Second pass: Parse nodes and ways
    uint32_t index = 0;
    size_t processed_elements = 0;
    size_t total_elements = node_count + way_count;
    int last_progress = -1;

    for (pugi::xml_node elem = root.first_child(); elem; elem = elem.next_sibling()) {
        const char* name = elem.name();
        if (strcmp(name, "node") == 0) {
            uint64_t id = elem.attribute("id").as_ullong();
            double lat = elem.attribute("lat").as_double();
            double lon = elem.attribute("lon").as_double();
            if (relevant_node_ids.find(id) != relevant_node_ids.end()) {
                node_id_to_index[id] = index;
                index_to_node_id.push_back(id);
                kd_tree.insert({lat, lon}, index); // Pass index here
                ++index;
                node_id_to_coords[id] = std::make_pair(lat, lon);
            }
        } else if (strcmp(name, "way") == 0) {
            std::vector<uint64_t> node_refs;
            for (pugi::xml_node nd = elem.child("nd"); nd; nd = nd.next_sibling("nd")) {
                uint64_t node_id = nd.attribute("ref").as_ullong();
                node_refs.push_back(node_id);
            }

            bool has_relevant_tag = false;
            std::string way_type;
            for (pugi::xml_node tag = elem.child("tag"); tag; tag = tag.next_sibling("tag")) {
                const char* key = tag.attribute("k").value();
                const char* value = tag.attribute("v").value();
                if (strcmp(key, "highway") == 0 ||
                    strcmp(key, "cycleway") == 0 ||
                    strcmp(key, "cycleway:left") == 0 ||
                    strcmp(key, "cycleway:right") == 0 ||
                    strcmp(key, "railway") == 0 ||
                    strcmp(key, "footway") == 0 ||
                    strcmp(key, "sidewalk") == 0){
                    has_relevant_tag = true;
                    way_type = value;
                    break;
                }
            }

            if (has_relevant_tag) {
                // Store the way type for all nodes in this way
                for (uint64_t node_id : node_refs) {
                    node_tags[node_id] = way_type;
                }

                // Add edges between consecutive nodes
                for (size_t i = 0; i < node_refs.size() - 1; ++i) {
                    auto from_it = node_id_to_index.find(node_refs[i]);
                    auto to_it = node_id_to_index.find(node_refs[i + 1]);
                    if (from_it != node_id_to_index.end() && to_it != node_id_to_index.end()) {
                        uint32_t from = from_it->second;
                        uint32_t to = to_it->second;
                        double lat1 = kd_tree.getPoint(from)[0];
                        double lon1 = kd_tree.getPoint(from)[1];
                        double lat2 = kd_tree.getPoint(to)[0];
                        double lon2 = kd_tree.getPoint(to)[1];
                        double weight = haversine_distance(lat1, lon1, lat2, lon2);
                        kd_tree.insertEdge(from, to, weight);
                        kd_tree.insertEdge(to, from, weight); // Assuming undirected graph
                    }
                }
            }
        }

        // Update progress
        ++processed_elements;
        int progress = static_cast<int>((processed_elements * 100.0) / total_elements);
        if(last_progress != progress)
        {
            last_progress = progress;
            std::cout << "\rLoading graph: " << progress << "%";
            std::cout.flush();
        }
    }

    std::vector<Relation> relations;
    for (pugi::xml_node rel = root.child("relation"); rel; rel = rel.next_sibling("relation")) {
        Relation relation;
        relation.id = rel.attribute("id").as_ullong();
        
        // Process relation tags
        for (pugi::xml_node tag = rel.child("tag"); tag; tag = tag.next_sibling("tag")) {
            std::string key = tag.attribute("k").value();
            std::string value = tag.attribute("v").value();
            relation.tags[key] = value;
            
            if (key == "type") relation.type = value;
            if (key == "route") relation.route_type = value;
        }
        
        // Process relation members
        for (pugi::xml_node member = rel.child("member"); member; member = member.next_sibling("member")) {
            RelationMember rel_member;
            rel_member.type = member.attribute("type").value();
            rel_member.ref = member.attribute("ref").as_ullong();
            rel_member.role = member.attribute("role").value();
            relation.members.push_back(rel_member);
        }
        
        relations.push_back(relation);
    }

    // Process relations after all nodes and ways are loaded
    for (const auto& relation : relations) {
        process_public_transport_relation(relation, kd_tree, node_id_to_index, node_tags);
    }

    std::cout << std::endl; // Move to the next line after progress is complete

    // Further processing if needed, such as filtering based on node_tags and whitelist flags

    return true;
}


// Helper function to determine if a node is allowed based on whitelist
bool is_node_allowed(uint64_t node_id, const std::unordered_map<uint64_t, std::string>& node_tags,
                    bool pedestrian, bool riding, bool driving, bool pubTransport) {
    // return true;
    if(pedestrian && riding && driving && pubTransport) return true;
    auto it = node_tags.find(node_id);
    if (it == node_tags.end()) return false;

    const std::string& v = it->second;

    if (pedestrian && pedes_white_list.count(v)) return true;
    if (riding && riding_white_list.count(v)) return true;
    if (driving && driving_white_list.count(v)) return true;
    if (pubTransport && pub_transport_white_list.count(v)) return true;

    return false;
}

double get_factor(uint64_t node_id, const std::unordered_map<uint64_t, std::string>& node_tags,
                    bool pedestrian, bool riding, bool driving, bool pubTransport,
                    int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed) {

    auto it = node_tags.find(node_id);
    if (it == node_tags.end()) return 1.0;

    const std::string& v = it->second;

    double ret = 1.0;
    if (pedestrian && pedes_white_list.count(v))           ret = 1 / pedSpeed;
    if (riding && riding_white_list.count(v))              ret = 1 / rideSpeed;
    if (driving && driving_white_list.count(v))            ret = 1 / driveSpeed;
    if (pubTransport && pub_transport_white_list.count(v)) ret = 1 / pubSpeed;

    return ret;
}


// Function to find the shortest path using Dijkstra's algorithm
std::vector<uint32_t> dijkstra(const KdTree& kd_tree, uint32_t start, uint32_t end,
                               const std::unordered_map<uint64_t, std::string>& node_tags,
                               bool pedestrian, bool riding, bool driving, bool pubTransport,
                               bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed) {
    std::vector<double> distances(kd_tree.size(), std::numeric_limits<double>::infinity());
    std::vector<uint32_t> previous(kd_tree.size(), -1);
    std::priority_queue<std::pair<double, uint32_t>,
                        std::vector<std::pair<double, uint32_t>>,
                        std::greater<std::pair<double, uint32_t>>> queue;

    distances[start] = 0.0;
    queue.emplace(0.0, start);

    #ifdef DEBUG
    std::cout << "[DEBUG] Starting Dijkstra's algorithm from node " << start << " to node " << end << std::endl;
    #endif

    while (!queue.empty()) {
        auto [dist, current] = queue.top();
        queue.pop();

        #ifdef DEBUG
        std::cout << "[DEBUG] Visiting node " << current << " with current distance " << dist << std::endl;
        #endif

        if (current == end) {
            #ifdef DEBUG
            std::cout << "[DEBUG] Reached the destination node " << end << std::endl;
            #endif
            break;
        }

        if (dist > distances[current]) continue;

        for (const auto& edge : kd_tree.getEdges(current)) {
            uint32_t neighbor = edge.first;
            double weight = edge.second;
            if (speed_first_enabled) {
                uint64_t neighbor_id = index_to_node_id[neighbor];
                weight *= get_factor(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport, pedSpeed, rideSpeed, driveSpeed, pubSpeed);
            }
            double new_dist = dist + weight;

            // Get node_id from index_to_node_id
            uint64_t neighbor_id = index_to_node_id[neighbor];

            // Check whitelist
            if (!is_node_allowed(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport)) {
                #ifdef DEBUG
                std::cout << "[DEBUG] Node " << neighbor << " is not allowed based on the whitelist" << std::endl;
                #endif
                continue;
            }

            #ifdef DEBUG
            std::cout << "[DEBUG] Checking neighbor node " << neighbor << " with edge weight " << edge.second << std::endl;
            #endif

            if (new_dist < distances[neighbor]) {
                distances[neighbor] = new_dist;
                previous[neighbor] = current;
                queue.emplace(new_dist, neighbor);
                #ifdef DEBUG
                std::cout << "[DEBUG] Updated distance for node " << neighbor << " to " << new_dist << std::endl;
                #endif
            }
        }
    }

    // Reconstruct path
    std::vector<uint32_t> path;
    if (distances[end] == std::numeric_limits<double>::infinity()) {
        #ifdef DEBUG
        std::cout << "[DEBUG] No path found to node " << end << std::endl;
        #endif
        return path; // No path found
    }

    for (uint32_t at = end; at != start; at = previous[at]) {
        path.push_back(at);
        if (previous[at] == static_cast<uint32_t>(-1)) {
            #ifdef DEBUG
            std::cout << "[DEBUG] No path found during reconstruction" << std::endl;
            #endif
            return std::vector<uint32_t>(); // No path found
        }
    }
    path.push_back(start);
    std::reverse(path.begin(), path.end());

    #ifdef DEBUG
    std::cout << "[DEBUG] Path found: ";
    for (uint32_t node : path) {
        std::cout << node << " ";
    }
    std::cout << std::endl;
    #endif

    return path;
}

// Function to find the shortest path using Bidirectional A* algorithm
std::vector<uint32_t> a_star(const KdTree& kd_tree, uint32_t start, uint32_t end,
                             const std::vector<std::pair<double, double>>& coords,
                             const std::unordered_map<uint64_t, std::string>& node_tags,
                             bool pedestrian, bool riding, bool driving, bool pubTransport,
                             bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed) {
    // Haversine distance heuristic
    auto heuristic = [&kd_tree](uint32_t a, uint32_t b) {
        const double R = 6371000.0; // Earth's radius in meters
        std::vector<double> point_a = kd_tree.getPoint(a);
        std::vector<double> point_b = kd_tree.getPoint(b);
        
        double lat1 = point_a[0] * M_PI / 180.0;
        double lat2 = point_b[0] * M_PI / 180.0;
        double dLat = lat2 - lat1;
        double dLon = (point_b[1] - point_a[1]) * M_PI / 180.0;
        
        double a_val = sin(dLat/2) * sin(dLat/2) +
                      cos(lat1) * cos(lat2) * 
                      sin(dLon/2) * sin(dLon/2);
        double c = 2 * atan2(sqrt(a_val), sqrt(1-a_val));
        
        return static_cast<float>(R * c);
    };

    std::vector<float> g_score_start(kd_tree.size(), std::numeric_limits<float>::infinity());
    std::vector<float> g_score_end(kd_tree.size(), std::numeric_limits<float>::infinity());
    std::vector<float> f_score_start(kd_tree.size(), std::numeric_limits<float>::infinity());
    std::vector<float> f_score_end(kd_tree.size(), std::numeric_limits<float>::infinity());
    std::vector<uint32_t> came_from_start(kd_tree.size(), -1);
    std::vector<uint32_t> came_from_end(kd_tree.size(), -1);

    g_score_start[start] = 0.0f;
    f_score_start[start] = heuristic(start, end);
    g_score_end[end] = 0.0f;
    f_score_end[end] = heuristic(end, start);

    auto cmp_start = [&f_score_start](uint32_t a, uint32_t b) {
        return f_score_start[a] > f_score_start[b];
    };
    auto cmp_end = [&f_score_end](uint32_t a, uint32_t b) {
        return f_score_end[a] > f_score_end[b];
    };

    std::priority_queue<uint32_t, std::vector<uint32_t>, decltype(cmp_start)> open_set_start(cmp_start);
    std::priority_queue<uint32_t, std::vector<uint32_t>, decltype(cmp_end)> open_set_end(cmp_end);

    open_set_start.push(start);
    open_set_end.push(end);

    std::unordered_set<uint32_t> closed_set_start, closed_set_end;

    while (!open_set_start.empty() && !open_set_end.empty()) {
        // Process from start
        uint32_t current_start = open_set_start.top();
        open_set_start.pop();
        closed_set_start.insert(current_start);

        if (closed_set_end.find(current_start) != closed_set_end.end()) {
            // Path found - reconstruct the path
            std::vector<uint32_t> path;
            uint32_t meeting_node = current_start;

            // Reconstruct path from start to meeting_node
            uint32_t u = meeting_node;
            while (u != start) {
                path.push_back(u);
                u = came_from_start[u];
            }
            path.push_back(start);
            std::reverse(path.begin(), path.end());

            // Reconstruct path from meeting_node to end
            u = came_from_end[meeting_node];
            while (u != end) {
                path.push_back(u);
                u = came_from_end[u];
            }
            path.push_back(end);

            return path;
        }

        for (const auto& edge : kd_tree.getEdges(current_start)) {
            if (closed_set_start.find(edge.first) != closed_set_start.end()) continue;

            float weight = edge.second;
            if (speed_first_enabled) {
                uint64_t neighbor_id = index_to_node_id[edge.first];
                weight *= get_factor(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport, pedSpeed, rideSpeed, driveSpeed, pubSpeed);
            }
            float tentative_g_score = g_score_start[current_start] + weight;

            // Get node_id from index_to_node_id
            uint64_t neighbor_id = index_to_node_id[edge.first];

            // Check whitelist
            if (!is_node_allowed(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport))
                continue;

            if (tentative_g_score < g_score_start[edge.first]) {
                came_from_start[edge.first] = current_start;
                g_score_start[edge.first] = tentative_g_score;
                f_score_start[edge.first] = g_score_start[edge.first] + heuristic(edge.first, end);
                open_set_start.push(edge.first);
            }
        }

        // Process from end
        uint32_t current_end = open_set_end.top();
        open_set_end.pop();
        closed_set_end.insert(current_end);

        if (closed_set_start.find(current_end) != closed_set_start.end()) {
            // Path found - reconstruct the path
            std::vector<uint32_t> path;
            uint32_t meeting_node = current_end;

            // Reconstruct path from start to meeting_node
            uint32_t u = meeting_node;
            while (u != start) {
                path.push_back(u);
                u = came_from_start[u];
            }
            path.push_back(start);
            std::reverse(path.begin(), path.end());

            // Reconstruct path from meeting_node to end
            u = came_from_end[meeting_node];
            while (u != end) {
                path.push_back(u);
                u = came_from_end[u];
            }
            path.push_back(end);

            return path;
        }

        for (const auto& edge : kd_tree.getEdges(current_end)) {
            if (closed_set_end.find(edge.first) != closed_set_end.end()) continue;

            float weight = edge.second;
            if (speed_first_enabled) {
                uint64_t neighbor_id = index_to_node_id[edge.first];
                weight *= get_factor(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport, pedSpeed, rideSpeed, driveSpeed, pubSpeed);
            }
            float tentative_g_score = g_score_end[current_end] + weight;

            // Get node_id from index_to_node_id
            uint64_t neighbor_id = index_to_node_id[edge.first];

            // Check whitelist
            if (!is_node_allowed(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport))
                continue;

            if (tentative_g_score < g_score_end[edge.first]) {
                came_from_end[edge.first] = current_end;
                g_score_end[edge.first] = tentative_g_score;
                f_score_end[edge.first] = g_score_end[edge.first] + heuristic(edge.first, start);
                open_set_end.push(edge.first);
            }
        }
    }

    return {}; // No path found
}

// Function to find the shortest path using Bellman-Ford algorithm
std::vector<uint32_t> bellman_ford(const KdTree& kd_tree, uint32_t start, uint32_t end,
                                   const std::unordered_map<uint64_t, std::string>& node_tags,
                                   bool pedestrian, bool riding, bool driving, bool pubTransport,
                                   bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed) {
    std::vector<float> distances(kd_tree.size(), std::numeric_limits<float>::infinity());
    std::vector<uint32_t> previous(kd_tree.size(), -1);

    distances[start] = 0.0f;

    int cur_progress = 0;

    for (size_t i = 0; i < kd_tree.size() - 1; ++i) {
        for (size_t u = 0; u < kd_tree.size(); ++u) {
            for (const auto& edge : kd_tree.getEdges(u)) {
                // Get node_id from index_to_node_id
                uint64_t neighbor_id = index_to_node_id[edge.first];

                if (!is_node_allowed(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport))
                    continue;

                float weight = edge.second;
                if (speed_first_enabled) {
                    uint64_t neighbor_id = index_to_node_id[edge.first];
                    weight *= get_factor(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport, pedSpeed, rideSpeed, driveSpeed, pubSpeed);
                }
                if (distances[u] + weight < distances[edge.first]) {
                    distances[edge.first] = distances[u] + weight;
                    previous[edge.first] = u;
                }
            }
        }
        int progress = static_cast<int>((i * 100.0) / kd_tree.size());
        if (progress <= 100 && progress > cur_progress) {
            std::cout << progress << std::endl;
            cur_progress = progress;
        }
    }

    // Reconstruct path
    std::vector<uint32_t> path;
    uint32_t u = end;
    if (previous[u] != -1 || u == start) {
        while (u != start) {
            path.push_back(u);
            u = previous[u];
        }
        path.push_back(start);
        std::reverse(path.begin(), path.end());
    }

    return path;
}

// Function to find the shortest path using Floyd-Warshall algorithm
std::vector<uint32_t> floyd_warshall(const KdTree& kd_tree, uint32_t start, uint32_t end,
                                     const std::unordered_map<uint64_t, std::string>& node_tags,
                                     bool pedestrian, bool riding, bool driving, bool pubTransport,
                                     bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed) {
    std::vector<std::vector<float>> dist(kd_tree.size(), std::vector<float>(kd_tree.size(), std::numeric_limits<float>::infinity()));
    std::vector<std::vector<uint32_t>> next(kd_tree.size(), std::vector<uint32_t>(kd_tree.size(), -1));

    for (size_t u = 0; u < kd_tree.size(); ++u) {
        dist[u][u] = 0.0f;
        for (const auto& edge : kd_tree.getEdges(u)) {
            // Get node_id from index_to_node_id
            uint64_t neighbor_id = index_to_node_id[edge.first];

            if (!is_node_allowed(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport))
                continue;

            float weight = edge.second;
            if (speed_first_enabled) {
                uint64_t neighbor_id = index_to_node_id[edge.first];
                weight *= get_factor(neighbor_id, node_tags, pedestrian, riding, driving, pubTransport, pedSpeed, rideSpeed, driveSpeed, pubSpeed);
            }
            dist[u][edge.first] = weight;
            next[u][edge.first] = edge.first;
        }
    }

    size_t total_nodes = kd_tree.size();
    size_t processed_nodes = 0;
    int last_progress = 0;

    for (size_t k = 0; k < kd_tree.size(); ++k) {
        for (size_t i = 0; i < kd_tree.size(); ++i) {
            for (size_t j = 0; j < kd_tree.size(); ++j) {
                if (dist[i][k] + dist[k][j] < dist[i][j]) {
                    dist[i][j] = dist[i][k] + dist[k][j];
                    next[i][j] = next[i][k];
                }
            }
        }

        processed_nodes++;
        int progress = static_cast<int>((processed_nodes * 100.0) / total_nodes);
        if (progress > last_progress) {
            std::cout << "Progress: " << progress << std::endl;
            last_progress = progress;
        }
    }
    

    // Reconstruct path
    std::vector<uint32_t> path;
    if (next[start][end] != -1) {
        uint32_t u = start;
        while (u != end) {
            path.push_back(u);
            u = next[u][end];
        }
        path.push_back(end);
    }

    return path;
}

uint64_t get_nearest_node_id(const KdTree& kd_tree, double lat, double lon,
                             const std::unordered_map<uint64_t, std::string>& node_tags,
                             bool pedestrian, bool riding, bool driving, bool pubTransport) {
    std::vector<double> point = {lat, lon};
    int k = 1;

    static const int MAXK = 50;

    while (k < MAXK) {
        std::vector<std::vector<double>> nearest_points = kd_tree.findKthNearestNeighbor(point, k);
        if (!nearest_points.empty()) {
            const auto& nearest_point = nearest_points.back(); // Only process the k-th nearest point
            auto it = std::find(kd_tree.points.begin(), kd_tree.points.end(), nearest_point);
            if (it != kd_tree.points.end()) {
                size_t index = std::distance(kd_tree.points.begin(), it);
                if (index < index_to_node_id.size()) { // Ensure index is within bounds
                    uint64_t node_id = index_to_node_id[index];
                    if (is_node_allowed(node_id, node_tags, pedestrian, riding, driving, pubTransport)) {
                        return node_id;
                    }
                }
            }
        }
        k++;
    }

    return 0; // Return 0 if no nearest node is found
}

void generate_place_name_dictionary(const std::string& osm_filepath, const std::string& output_file) {
    pugi::xml_document doc;
    if (!doc.load_file(osm_filepath.c_str())) {
        std::cerr << "Failed to load file: " << osm_filepath << std::endl;
        return;
    }

    std::unordered_map<std::string, std::pair<double, double>> name_to_coords;
    std::unordered_map<uint64_t, std::pair<double, double>> node_coords;
    pugi::xml_node root = doc.child("osm");

    // Count total elements for progress calculation
    size_t total_elements = 0;
    for (pugi::xml_node node = root.child("node"); node; node = node.next_sibling("node")) {
        ++total_elements;
    }
    for (pugi::xml_node way = root.child("way"); way; way = way.next_sibling("way")) {
        ++total_elements;
    }

    size_t processed_elements = 0;
    int last_progress = -1;

    // First pass: Collect node coordinates and names
    for (pugi::xml_node node = root.child("node"); node; node = node.next_sibling("node")) {
        uint64_t id = node.attribute("id").as_ullong();
        double lat = node.attribute("lat").as_double();
        double lon = node.attribute("lon").as_double();
        node_coords[id] = {lat, lon};

        for (pugi::xml_node tag = node.child("tag"); tag; tag = tag.next_sibling("tag")) {
            const char* key = tag.attribute("k").value();
            if (strcmp(key, "name") == 0) {
                const char* name = tag.attribute("v").value();
                name_to_coords[name] = {lat, lon};
                break; // Only need one name per node
            }
        }

        // Update progress
        ++processed_elements;
        int progress = static_cast<int>((processed_elements * 100.0) / total_elements);
        if (progress > last_progress) {
            last_progress = progress;
            std::cout << "Dic generation progress: " << progress << std::endl;
        }
    }

    // Second pass: Collect way names and associate with the first node's coordinates
    for (pugi::xml_node way = root.child("way"); way; way = way.next_sibling("way")) {
        std::string name;
        bool has_name = false;
        for (pugi::xml_node tag = way.child("tag"); tag; tag = tag.next_sibling("tag")) {
            const char* key = tag.attribute("k").value();
            if (strcmp(key, "name") == 0) {
                name = tag.attribute("v").value();
                has_name = true;
                break;
            }
        }

        if (has_name) {
            // Get the first node reference to get coordinates
            pugi::xml_node nd = way.child("nd");
            if (nd) {
                uint64_t ref = nd.attribute("ref").as_ullong();
                auto it = node_coords.find(ref);
                if (it != node_coords.end()) {
                    name_to_coords[name] = it->second;
                }
            }
        }

        // Update progress
        ++processed_elements;
        int progress = static_cast<int>((processed_elements * 100.0) / total_elements);
        if (progress > last_progress) {
            last_progress = progress;
            std::cout << progress << std::endl;
        }
    }

    // Write the dictionary to the output file
    std::ofstream outfile(output_file);
    if (!outfile.is_open()) {
        std::cerr << "Failed to open output file: " << output_file << std::endl;
        return;
    }

    outfile.precision(10); // Set precision to 10 decimal places
    outfile << std::fixed; // Use fixed-point notation

    for (const auto& entry : name_to_coords) {
        outfile << entry.first << " " << entry.second.first << " " << entry.second.second << std::endl;
    }

    outfile.close();
}
