// FormalFlow-Scout optional C++17 graph core.
//
// This is a performance sibling of the pure-Python graph core. The Python path
// is ALWAYS authoritative and always works with no compiler; this binary is
// only used when explicitly built and requested (`--use-cpp`), and the CLI
// cross-checks its result against Python before trusting it.
//
// Contract (JSON over stdin -> stdout):
//   in : {"n": N, "edges": [[src,dst,kind],...], "seeds":[...],
//         "combinational_only": bool}
//   out: {"coi": [sorted node ids]}
//
// Edge-kind ints match Python's list(EdgeKind): 0=COMB 1=SEQ 2=CLOCK 3=RESET
// 4=HIER. For COI we traverse COMB(0), HIER(4) always, and SEQ(1) when not
// combinational_only. CLOCK/RESET are control fanout and are NOT followed here
// (the Python cross-check uses include_control matching this policy: the CLI
// compares against combinational_only=False, include_control follows suit only
// when the caller sets it - see cpp_bridge which requests the data COI).
//
// Data layout: CSR (compressed sparse row). One flat `adj` array grouped by
// source with an `offsets` index. Sequential scan per node = cache friendly,
// no per-node heap allocation. Deterministic: output ids are sorted.
//
// Deliberately dependency-free: a tiny hand-rolled JSON reader for exactly this
// schema (integers, arrays, the two known keys). Not a general JSON parser.

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace {

struct Input {
    int64_t n = 0;
    std::vector<std::array<int64_t, 3>> edges;
    std::vector<int64_t> seeds;
    bool combinational_only = false;
};

// Minimal scanner over the fixed schema. Extracts integers following each key.
std::string slurp_stdin() {
    std::ostringstream ss;
    ss << std::cin.rdbuf();
    return ss.str();
}

std::vector<int64_t> read_int_array(const std::string& s, size_t& i) {
    std::vector<int64_t> out;
    while (i < s.size() && s[i] != '[') ++i;
    if (i < s.size()) ++i;  // skip '['
    int depth = 1;
    std::string num;
    auto flush = [&]() {
        if (!num.empty()) { out.push_back(std::stoll(num)); num.clear(); }
    };
    while (i < s.size() && depth > 0) {
        char c = s[i];
        if (c == '[') { ++depth; }
        else if (c == ']') { flush(); --depth; }
        else if (c == ',') { flush(); }
        else if (c == '-' || std::isdigit((unsigned char)c)) { num.push_back(c); }
        ++i;
    }
    return out;
}

Input parse(const std::string& s) {
    Input in;
    size_t p;
    if ((p = s.find("\"n\"")) != std::string::npos) {
        size_t i = p + 3;
        while (i < s.size() && (s[i] == ':' || std::isspace((unsigned char)s[i]))) ++i;
        std::string num;
        while (i < s.size() && (std::isdigit((unsigned char)s[i]) || s[i]=='-')) num.push_back(s[i++]);
        in.n = num.empty() ? 0 : std::stoll(num);
    }
    if ((p = s.find("\"edges\"")) != std::string::npos) {
        size_t i = p;
        auto flat = read_int_array(s, i);  // flattened [src,dst,kind, src,dst,kind,...]
        for (size_t k = 0; k + 3 <= flat.size(); k += 3) {
            in.edges.push_back({flat[k], flat[k + 1], flat[k + 2]});
        }
    }
    if ((p = s.find("\"seeds\"")) != std::string::npos) {
        size_t i = p;
        in.seeds = read_int_array(s, i);
    }
    in.combinational_only = s.find("\"combinational_only\": true") != std::string::npos
        || s.find("\"combinational_only\":true") != std::string::npos;
    return in;
}

}  // namespace

int main() {
    std::string s = slurp_stdin();
    Input in = parse(s);
    const int64_t n = in.n;

    // Build CSR.
    std::vector<int64_t> degree(n, 0);
    for (auto& e : in.edges) if (e[0] >= 0 && e[0] < n) degree[e[0]]++;
    std::vector<int64_t> offsets(n + 1, 0);
    for (int64_t i = 0; i < n; ++i) offsets[i + 1] = offsets[i] + degree[i];
    std::vector<int64_t> adj(offsets[n]);
    std::vector<int8_t> kind(offsets[n]);
    std::vector<int64_t> cursor(offsets.begin(), offsets.begin() + n);
    for (auto& e : in.edges) {
        if (e[0] < 0 || e[0] >= n) continue;
        int64_t pos = cursor[e[0]]++;
        adj[pos] = e[1];
        kind[pos] = (int8_t)e[2];
    }

    // Match the analyzer's default report policy: follow COMB, HIER, CLOCK and
    // RESET always, and SEQ unless combinational_only. The CLI cross-checks this
    // against Python's backward_coi(..., include_control=True) before trusting
    // the result, so both cores compute an identical set.
    auto allowed = [&](int8_t k) -> bool {
        if (k == 0 || k == 4) return true;         // COMB, HIER
        if (k == 2 || k == 3) return true;         // CLOCK, RESET
        if (k == 1) return !in.combinational_only; // SEQ
        return false;
    };

    std::vector<char> visited(n, 0);
    std::vector<int64_t> stack;
    for (int64_t sd : in.seeds) {
        if (sd >= 0 && sd < n && !visited[sd]) { visited[sd] = 1; stack.push_back(sd); }
    }
    while (!stack.empty()) {
        int64_t cur = stack.back(); stack.pop_back();
        for (int64_t j = offsets[cur]; j < offsets[cur + 1]; ++j) {
            if (allowed(kind[j]) && !visited[adj[j]]) {
                visited[adj[j]] = 1;
                stack.push_back(adj[j]);
            }
        }
    }
    std::vector<int64_t> coi;
    for (int64_t i = 0; i < n; ++i) if (visited[i]) coi.push_back(i);
    std::sort(coi.begin(), coi.end());

    std::cout << "{\"coi\": [";
    for (size_t i = 0; i < coi.size(); ++i) {
        if (i) std::cout << ",";
        std::cout << coi[i];
    }
    std::cout << "]}\n";
    return 0;
}
