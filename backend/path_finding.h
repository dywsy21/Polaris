#ifndef PATH_FINDING_H
#define PATH_FINDING_H

#include <vector>
#include <unordered_map>
#include <utility>
#include <cstdint>
#include <string>
#include <unordered_set>
#include "k-dtree.h"

extern std::vector<uint64_t> index_to_node_id;
extern std::unordered_map<uint64_t, std::pair<double, double>> node_id_to_coords;



// Define Edge structure
struct Edge {
    uint32_t to;
    double weight;
};

struct RelationMember {
    std::string type;
    uint64_t ref;
    std::string role;
};

struct Relation {
    uint64_t id;
    std::string type;
    std::string route_type;
    std::vector<RelationMember> members;
    std::unordered_map<std::string, std::string> tags;
};

// Function declarations with whitelist parameters and correct node_tags type
std::vector<uint32_t> dijkstra(const KdTree& kd_tree, uint32_t start, uint32_t end,
                               const std::unordered_map<uint64_t, std::string>& node_tags,
                               bool pedestrian, bool riding, bool driving, bool pubTransport,
                               bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed);

std::vector<uint32_t> a_star(const KdTree& kd_tree, uint32_t start, uint32_t end,
                             const std::vector<std::pair<double, double>>& coords,
                             const std::unordered_map<uint64_t, std::string>& node_tags,
                             bool pedestrian, bool riding, bool driving, bool pubTransport,
                             bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed);

std::vector<uint32_t> bellman_ford(const KdTree& kd_tree, uint32_t start, uint32_t end,
                                   const std::unordered_map<uint64_t, std::string>& node_tags,
                                   bool pedestrian, bool riding, bool driving, bool pubTransport,
                                   bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed);

std::vector<uint32_t> floyd_warshall(const KdTree& kd_tree, uint32_t start, uint32_t end,
                                     const std::unordered_map<uint64_t, std::string>& node_tags,
                                     bool pedestrian, bool riding, bool driving, bool pubTransport,
                                     bool speed_first_enabled, int pedSpeed, int rideSpeed, int driveSpeed, int pubSpeed);

// Declaration of load_graph function
bool load_graph(const std::string& filepath,
                std::unordered_map<uint64_t, uint32_t>& node_id_to_index,
                std::unordered_map<uint64_t, std::string>& node_tags,
                std::unordered_map<uint64_t, std::pair<double, double>>& node_id_to_coords,
                bool pedestrian, bool riding, bool driving, bool pubTransport,
                KdTree& kd_tree);

uint64_t get_nearest_node_id(const KdTree& kd_tree, double lat, double lon,
                             const std::unordered_map<uint64_t, std::string>& node_tags,
                             bool pedestrian, bool riding, bool driving, bool pubTransport);

// Declare the function to generate the place name dictionary
void generate_place_name_dictionary(const std::string& osm_filepath, const std::string& output_file);

void process_public_transport_relation(const Relation& relation,
                                     KdTree& kd_tree,
                                     const std::unordered_map<uint64_t, uint32_t>& node_id_to_index,
                                     std::unordered_map<uint64_t, std::string>& node_tags);

#endif // PATH_FINDING_H
