#pragma once

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

// Independent sampled-token budgets; injected delimiters consume context, not
// the answer allowance. No model-specific weights or sampling settings change.
class GenerationBudget {
public:
    enum class Phase { Undecided, Thought, Answer };
    Phase phase = Phase::Answer;
    int thought = 0;
    int answer = 0;
    int thought_limit = 512;
    int answer_limit = 250;
    bool forced = false;
    std::string opener;

    void reset(bool thinking, int answer_tokens, int thought_tokens = 512) {
        phase = thinking ? Phase::Undecided : Phase::Answer;
        thought = answer = 0;
        thought_limit = thought_tokens;
        answer_limit = answer_tokens;
        forced = false;
        pending.clear();
        opener.clear();
    }

    // Some Jinja templates put the opening thought delimiter in the prompt.
    void seed_prompt(const std::string & prompt) {
        if (phase != Phase::Undecided) return;
        const auto end = prompt.find_last_not_of(" \t\r\n");
        if (end == std::string::npos) return;
        for (const auto & marker : starts()) {
            if (end + 1 >= marker.size() &&
                prompt.compare(end + 1 - marker.size(), marker.size(), marker) == 0) {
                opener = marker;
                phase = Phase::Thought;
                return;
            }
        }
    }

    void observe(const std::string & piece) {
        if (phase == Phase::Answer) { ++answer; return; }
        ++thought;
        pending += piece;
        if (phase == Phase::Undecided) {
            auto first = pending.find_first_not_of(" \t\r\n");
            if (first == std::string::npos) return;
            const std::string text = pending.substr(first);
            for (const auto & marker : starts()) {
                if (text.compare(0, marker.size(), marker) == 0) {
                    opener = marker;
                    phase = Phase::Thought;
                    pending = text.substr(marker.size());
                    break;
                }
                if (marker.compare(0, text.size(), text) == 0) return;
            }
            if (phase == Phase::Undecided) {
                // Thinking enabled but the model answered directly.
                phase = Phase::Answer;
                answer = thought;
                thought = 0;
                pending.clear();
                return;
            }
        }
        for (const auto & marker : ends()) {
            const auto pos = pending.find(marker);
            if (pos != std::string::npos) {
                // A token containing both delimiter and visible text also counts
                // once toward the answer budget.
                answer = pending.size() > pos + marker.size() ? 1 : 0;
                phase = Phase::Answer;
                pending.clear();
                return;
            }
        }
        if (pending.size() > 32) pending.erase(0, pending.size() - 32);
    }

    bool needs_final() const {
        return (phase == Phase::Thought && thought >= thought_limit) ||
            (phase == Phase::Undecided && thought >= std::max(32, thought_limit));
    }
    bool done() const { return phase == Phase::Answer && answer >= answer_limit; }
    bool in_thought() const { return phase == Phase::Thought; }
    std::string closer() const {
        if (opener == "<think>" || opener == "<|think|>") return "</think>";
        if (opener == "<|channel>analysis") return "<|channel>final";
        return "<channel|>";
    }
    void force_final() {
        phase = Phase::Answer;
        answer = 0;
        forced = true;
        pending.clear();
    }

private:
    std::string pending;
    static const std::vector<std::string> & starts() {
        static const std::vector<std::string> v = {
            "<|channel>thought", "<|channel>analysis", "<think>", "<|think|>"
        };
        return v;
    }
    static const std::vector<std::string> & ends() {
        static const std::vector<std::string> v = {"<channel|>", "</think>", "<|channel>final"};
        return v;
    }
};
