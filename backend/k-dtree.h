#ifndef KDTREE_H
#define KDTREE_H

#include <vector>
#include <memory>
#include <unordered_map>
#include <queue> // Include for priority_queue
#include <utility> // Include for pair
#include <iostream>

class KdTree {
public:
    KdTree(int k);
    ~KdTree();

    void insert(const std::vector<double>& point, uint32_t index);
    bool search(const std::vector<double>& point) const;
    std::vector<double> findMin(int dim) const;
    void deletePoint(const std::vector<double>& point);
    std::vector<double> findNearestNeighbor(const std::vector<double>& point) const;
    void insertEdge(uint32_t from, uint32_t to, double weight);
    const std::vector<std::pair<uint32_t, double>>& getEdges(uint32_t node_index) const;
    size_t size() const;
    void reserve(size_t n);
    const std::vector<double>& getPoint(uint32_t index) const;
    std::vector<std::vector<double>> findKthNearestNeighbor(const std::vector<double>& point, int k) const;

    std::vector<std::vector<double>> points; // Add this line to declare the points member variable

private:
    struct Node {
        std::vector<double> point;
        uint32_t index; // Add this line
        std::unique_ptr<Node> left;
        std::unique_ptr<Node> right;
        std::vector<std::pair<uint32_t, double>> edges;

        Node(const std::vector<double>& point, uint32_t index)
            : point(point), index(index), left(nullptr), right(nullptr) {}
    };

    std::unique_ptr<Node> root;
    int k;
    size_t tree_size;

    std::unique_ptr<Node> insertRec(std::unique_ptr<Node> node, const std::vector<double>& point, uint32_t index, int depth);
    bool searchRec(const Node* node, const std::vector<double>& point, int depth) const;
    std::unique_ptr<Node> deleteRec(std::unique_ptr<Node> node, const std::vector<double>& point, int depth);
    const Node* findMinRec(const Node* node, int dim, int depth) const;
    const Node* findNearestNeighborRec(const Node* node, const std::vector<double>& point, int depth, const Node* best, double& bestDist) const;
    void findKthNearestNeighborRec(const Node* node, const std::vector<double>& point, int depth, int k,
                                   std::priority_queue<std::pair<double, const Node*>>& max_heap) const;
    std::unordered_map<uint32_t, Node*> index_to_node; // Map indices to nodes

    // Define a custom key type for the cache
    struct CacheKey {
        std::vector<double> point;
        int k;

        bool operator==(const CacheKey& other) const {
            return point == other.point && k == other.k;
        }
    };

    struct CacheKeyHash {
        std::size_t operator()(const CacheKey& key) const {
            std::size_t hash1 = std::hash<int>()(key.k);
            std::size_t hash2 = 0;
            for (const auto& val : key.point) {
                hash2 ^= std::hash<double>()(val) + 0x9e3779b9 + (hash2 << 6) + (hash2 >> 2);
            }
            return hash1 ^ hash2;
        }
    };

    mutable std::unordered_map<CacheKey, std::vector<std::vector<double>>, CacheKeyHash> cache; // Update cache to use custom key type
};

#endif // KDTREE_H
