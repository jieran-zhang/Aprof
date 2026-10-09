#pragma once
#include <fstream>
#include <string>
inline bool ReadFile(const std::string&p,void*d,size_t n){std::ifstream f(p,std::ios::binary);return f&&bool(f.read(static_cast<char*>(d),n));}
inline bool WriteFile(const std::string&p,const void*d,size_t n){std::ofstream f(p,std::ios::binary);return f&&bool(f.write(static_cast<const char*>(d),n));}
