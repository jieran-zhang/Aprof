#pragma once
#include <fstream>
#include <string>
inline bool ReadFile(const std::string&p,void*d,size_t n){std::ifstream f(p,std::ios::binary);if(!f)return false;f.read(static_cast<char*>(d),n);return f.good()||static_cast<size_t>(f.gcount())==n;}
inline bool WriteFile(const std::string&p,const void*d,size_t n){std::ofstream f(p,std::ios::binary);if(!f)return false;f.write(static_cast<const char*>(d),n);return f.good();}
