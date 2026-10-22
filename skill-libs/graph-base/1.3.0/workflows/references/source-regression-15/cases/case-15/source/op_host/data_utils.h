#pragma once
#include <filesystem>
#include <fstream>
#include <string>
inline bool ReadFile(const std::string&p,void*d,size_t n){std::ifstream f(p,std::ios::binary);return f&&bool(f.read(reinterpret_cast<char*>(d),n));}inline bool WriteFile(const std::string&p,const void*d,size_t n){std::filesystem::path q(p);if(q.has_parent_path())std::filesystem::create_directories(q.parent_path());std::ofstream f(p,std::ios::binary);return f&&bool(f.write(reinterpret_cast<const char*>(d),n));}
