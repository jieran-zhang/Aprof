#pragma once
#include <fstream>
#include <string>
#include <vector>
inline bool ReadAll(const std::string&p,std::vector<uint8_t>&v){std::ifstream f(p,std::ios::binary|std::ios::ate);if(!f)return false;auto n=f.tellg();if(n<0)return false;v.resize(size_t(n));f.seekg(0);return bool(f.read(reinterpret_cast<char*>(v.data()),n));}
inline bool WriteAll(const std::string&p,const void*d,size_t n){std::ofstream f(p,std::ios::binary);return f&&bool(f.write(static_cast<const char*>(d),n));}
