#pragma once
#include <fstream>
#include <string>
inline bool ReadFile(const std::string&p,void*d,size_t n){std::ifstream f(p,std::ios::binary);return bool(f.read((char*)d,n));}
inline bool WriteFile(const std::string&p,const void*d,size_t n){std::ofstream f(p,std::ios::binary);return bool(f.write((const char*)d,n));}
